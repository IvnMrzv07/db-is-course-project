import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4, uuid5, UUID
from datetime import datetime, timezone, timedelta
from ingestion_service.infrastructure.database import partitioning
from ingestion_service.infrastructure.datasets.load_generator import load_snapshots

class Conflict(Exception):
    pass


class SnapshotChanged(Exception):
    """A staged reference points at input that is no longer available unchanged."""


@dataclass(frozen=True)
class ProductionLimits:
    """Batch size and how many documents of one job may be in flight (backpressure for slow or absent shards)."""

    batch_size: int = 500
    max_outstanding: int = 20_000
    load_documents: int = 20_000_000  # size of one `load-cs` job

    def __post_init__(self):
        # Content rejects batches above 1,000 documents; job counters are 32-bit integers.
        if not 1 <= self.batch_size <= 1000 or self.max_outstanding < self.batch_size \
                or not 1 <= self.load_documents < 2**31:
            raise ValueError('Invalid replay production limits')

    @classmethod
    def from_env(cls, env=os.environ):
        return cls(batch_size=int(env.get('REPLAY_BATCH_SIZE', cls.batch_size)),
                   max_outstanding=int(env.get('REPLAY_MAX_OUTSTANDING', cls.max_outstanding)),
                   load_documents=int(env.get('LOAD_DOCUMENTS', cls.load_documents)))

    def size_for(self, target_rate: int) -> int:
        """About ten batches per second for paced jobs; the full batch size at MAX (rate 0)."""
        return self.batch_size if target_rate == 0 else min(self.batch_size, max(1, target_rate // 10))

# Explicit allowlist of prepared snapshots; clients only choose among these IDs, never paths.
SNAPSHOTS = ('kaggle-cs', 'synthetic-cs')


def next_production(scheduled, now, documents, target_rate):
    """Schedule from the previous slot, not from now: otherwise the time spent staging each batch lowers the rate.
    A producer that fell behind catches up by at most one second."""
    if not target_rate:
        return now
    return max(scheduled, now - timedelta(seconds=1)) + timedelta(seconds=documents / target_rate)


class PreparedSnapshot:
    """Verified JSONL kept on disk; only line offsets stay in memory (~100k documents in total)."""

    def __init__(self, path, offsets):
        self.path, self.offsets = path, offsets

    def __len__(self):
        return len(self.offsets) - 1

    def __getitem__(self, window):
        start, stop, _ = window.indices(len(self))
        if start >= stop:
            return []
        with self.path.open('rb') as source:
            source.seek(self.offsets[start])
            return [json.loads(line) for line in source.read(self.offsets[stop] - self.offsets[start]).splitlines()]

    def window(self, job_id, job_created_at, start, end):
        return self[start:end]

    @classmethod
    def load(cls, path, manifest):
        digest, offsets = hashlib.sha256(), [0]
        with path.open('rb') as source:
            for line in source:
                digest.update(line)
                offsets.append(offsets[-1] + len(line))
        if digest.hexdigest() != manifest['jsonl_sha256']:
            raise ValueError('Prepared corpus checksum mismatch')
        snapshot = cls(path, offsets)
        if len(snapshot) != manifest['accepted']:
            raise ValueError('Prepared corpus count mismatch')
        return snapshot

class PostgresReplayStore:
    def __init__(self, pool, data_dir, partition_policy=None, limits=None):
        self.pool = pool
        self.data_dir = Path(data_dir)
        self.catalog = {}
        self.limits = limits or ProductionLimits()
        self.partition_policy = partition_policy or partitioning.PartitionPolicy()
        self._ready_days = frozenset()

    async def initialize(self):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('SELECT pg_advisory_xact_lock($1)', partitioning.MIGRATION_LOCK)
                await connection.execute(Path(__file__).with_name('migrations').joinpath('001_replay.sql').read_text())
                now = datetime.now(timezone.utc)
                report = await partitioning.migrate(connection, partitioning.migration_sql(), now, self.partition_policy.ahead_days)
                await connection.execute(Path(__file__).with_name('migrations').joinpath('003_high_load.sql').read_text())
                if report['converted'] or report['created']:
                    logging.getLogger(__name__).info('Replay partitioning migration: %s', report)
        self._ready_days = frozenset(partitioning.days_to_ensure(now, self.partition_policy.ahead_days))
        # Verify immutable prepared input once per process.
        for name in SNAPSHOTS:
            manifest_path = self.data_dir / f'{name}.manifest.json'
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                if manifest.get('snapshot_id', name) != name:
                    raise ValueError('Prepared manifest does not match its snapshot')
                self.catalog[name] = (manifest, PreparedSnapshot.load(self.data_dir / f'{name}.jsonl', manifest))
        self.catalog.update(load_snapshots(self.data_dir, self.limits.load_documents))

    async def snapshots(self):
        return [{'id': name, 'documents': manifest['accepted'], 'validation_rejected': manifest['rejected'],
                 'is_synthetic': bool(manifest.get('is_synthetic', False))}
                for name, (manifest, _) in self.catalog.items()]

    @staticmethod
    def view(row):
        if row is None:
            return None
        result = dict(row)
        result['id'] = str(result['id'])
        result['attempted'] = result['produced']
        result['backlog'] = result['produced'] - result['inserted'] - result['duplicates'] - result['rejected']
        for name in ('created_at', 'updated_at', 'next_at'):
            result[name] = result[name].isoformat()
        return result

    async def create_job(self, snapshot_id, rate, key):
        if snapshot_id not in self.catalog:
            raise ValueError('Unknown prepared snapshot')
        manifest, records = self.catalog[snapshot_id]
        request_hash = hashlib.sha256(f"{snapshot_id}:{manifest['jsonl_sha256']}:{rate}".encode()).hexdigest()
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute("""INSERT INTO replay_jobs
                  (id,idempotency_key,request_hash,snapshot_id,snapshot_hash,total,status,target_rate,validation_rejected)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT(idempotency_key) DO NOTHING""",
                  uuid4(),key,request_hash,snapshot_id,manifest['jsonl_sha256'],len(records),
                  'running' if records else 'completed',rate,manifest['rejected'])
                row = await connection.fetchrow('SELECT * FROM replay_jobs WHERE idempotency_key=$1',key)
                if row['request_hash'] != request_hash:
                    raise Conflict('Idempotency key already used with different parameters')
                return self.view(row)

    async def get_job(self, job_id):
        return self.view(await self.pool.fetchrow('SELECT * FROM replay_jobs WHERE id=$1',UUID(str(job_id))))

    async def list_jobs(self, page, page_size):
        rows = await self.pool.fetch('SELECT * FROM replay_jobs ORDER BY created_at DESC,id LIMIT $1 OFFSET $2',page_size,(page-1)*page_size)
        return {'items': [self.view(row) for row in rows], 'total': await self.pool.fetchval('SELECT count(*) FROM replay_jobs')}

    async def change_job(self, job_id, action, rate=None):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow('SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE',UUID(str(job_id)))
                if not row:
                    raise LookupError('Job not found')
                if row['status'] not in ('running','paused'):
                    raise Conflict('Completed or failed job cannot be changed; start a new replay to retry')
                if action == 'pause' and row['status'] != 'running' or action == 'resume' and row['status'] != 'paused':
                    raise Conflict('Invalid state transition')
                status = row['status'] if action == 'rate' else ('paused' if action == 'pause' else 'running')
                updated = await connection.fetchrow('UPDATE replay_jobs SET status=$2,target_rate=$3,next_at=now(),updated_at=now() WHERE id=$1 RETURNING *',
                    row['id'],status,rate if action == 'rate' else row['target_rate'])
                return self.view(updated)

    async def cancel_job(self, job_id):
        """Stop a job for good: staged but unpublished batches are dropped, published ones still complete."""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                row = await connection.fetchrow('SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE',UUID(str(job_id)))
                if not row:
                    raise LookupError('Job not found')
                if row['status'] not in ('running','paused'):
                    raise Conflict('Only a running or paused job can be cancelled')
                dropped = await connection.fetch("""UPDATE replay_outbox SET sent=true WHERE NOT sent AND created_at>=$2
                    AND id IN (SELECT id FROM replay_batches WHERE job_id=$1 AND created_at>=$2 AND status='pending') RETURNING id,created_at""",
                    row['id'],row['created_at'])
                await connection.executemany("UPDATE replay_batches SET status='cancelled' WHERE id=$1 AND created_at=$2",
                    [(batch['id'],batch['created_at']) for batch in dropped])
                return self.view(await connection.fetchrow("UPDATE replay_jobs SET status='cancelled',updated_at=now() WHERE id=$1 RETURNING *",row['id']))

    async def purge_jobs(self):
        """Delete the whole replay history; refused while a job could still produce or publish."""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('LOCK TABLE replay_jobs IN ACCESS EXCLUSIVE MODE')
                active = await connection.fetchval("SELECT count(*) FROM replay_jobs WHERE status IN ('running','paused')")
                if active:
                    raise Conflict(f'{active} active job(s): cancel them first')
                deleted = await connection.fetchval('SELECT count(*) FROM replay_jobs')
                await connection.execute('TRUNCATE replay_outbox, replay_batches, replay_jobs')
                return deleted

    async def ensure_partitions(self, now=None):
        """Create today's and upcoming partitions (also called on write after a UTC day rollover)."""
        now = now or datetime.now(timezone.utc)
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('SELECT pg_advisory_xact_lock($1)', partitioning.MAINTENANCE_LOCK)
                created = await partitioning.ensure_partitions(connection, now, self.partition_policy.ahead_days)
        self._ready_days = frozenset(partitioning.days_to_ensure(now, self.partition_policy.ahead_days))
        return created

    async def maintain_partitions(self, now=None, dry_run=False):
        """Background cycle: create upcoming partitions and drop expired ones (retention)."""
        result = await partitioning.maintain(self.pool, self.partition_policy, now=now, dry_run=dry_run)
        if not dry_run:
            self._ready_days = frozenset(partitioning.days_to_ensure(datetime.fromisoformat(result['now']),
                                                                     self.partition_policy.ahead_days))
        return result

    async def produce(self):
        if partitioning.utc_day(datetime.now(timezone.utc)) not in self._ready_days:
            try:  # rows would still be accepted by the DEFAULT partition, so never block producing
                await self.ensure_partitions()
            except Exception:
                logging.getLogger(__name__).exception('On-write partition creation failed; using DEFAULT partition')
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                job = await connection.fetchrow("""SELECT * FROM replay_jobs WHERE status='running' AND produced<total
                    AND next_at<=now() AND produced-inserted-duplicates-rejected<$1
                    ORDER BY next_at LIMIT 1 FOR UPDATE SKIP LOCKED""", self.limits.max_outstanding)
                if not job:
                    return False
                if self._records(job['snapshot_id'], job['snapshot_hash']) is None:
                    await connection.execute("UPDATE replay_jobs SET status='failed',error='Snapshot changed',updated_at=now() WHERE id=$1",job['id'])
                    return False
                start = job['produced']
                end = min(job['total'], start + self.limits.size_for(job['target_rate']))
                batch_id = uuid5(job['id'],str(start))
                # Reference only: the input is immutable, so the dispatcher rebuilds the documents when it publishes.
                # Full payloads stayed here for the whole retention period (~3 KB per document).
                reference = {'schema_version': 2, 'batch_id': str(batch_id), 'job_id': str(job['id']),
                    'prepared_at': job['created_at'].isoformat(), 'snapshot_id': job['snapshot_id'],
                    'snapshot_hash': job['snapshot_hash'], 'start': start, 'end': end}
                # Same created_at for batch and outbox row: composite FK, identical day partition.
                created_at = await connection.fetchval('INSERT INTO replay_batches(id,job_id,start_offset,end_offset) VALUES($1,$2,$3,$4) RETURNING created_at',
                    batch_id,job['id'],start,end)
                await connection.execute('INSERT INTO replay_outbox(id,payload,created_at) VALUES($1,$2::jsonb,$3)',batch_id,json.dumps(reference),created_at)
                await connection.execute('UPDATE replay_jobs SET produced=$2,next_at=$3,updated_at=now() WHERE id=$1',
                    job['id'],end,next_production(job['next_at'],datetime.now(timezone.utc),end-start,job['target_rate']))
                logging.getLogger(__name__).debug('Staged job=%s batch=%s end=%s', job['id'], batch_id, end)
                return True

    def _records(self, snapshot_id, snapshot_hash):
        manifest, records = self.catalog.get(snapshot_id, (None, None))
        return records if manifest and manifest['jsonl_sha256'] == snapshot_hash else None

    def materialize(self, payload):
        """Build the Content message from a staged reference (rows staged before references carry documents)."""
        if 'documents' in payload:
            return payload
        records = self._records(payload['snapshot_id'], payload['snapshot_hash'])
        if records is None:
            raise SnapshotChanged(payload['snapshot_id'])
        documents = records.window(UUID(payload['job_id']), datetime.fromisoformat(payload['prepared_at']),
                                   payload['start'], payload['end'])
        if len(documents) != payload['end'] - payload['start']:
            raise SnapshotChanged(payload['snapshot_id'])
        return {'schema_version': 1, 'batch_id': payload['batch_id'], 'job_id': payload['job_id'],
                'checkpoint': payload['end'], 'prepared_at': payload['prepared_at'], 'documents': documents}

    async def dispatch(self, publish, limit=20):
        """Publish staged batches; a row is marked sent only after the broker confirmed it."""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                rows = await connection.fetch('SELECT id,created_at,payload FROM replay_outbox WHERE NOT sent ORDER BY created_at LIMIT $1 FOR UPDATE SKIP LOCKED', limit)
                for row in rows:
                    payload = json.loads(row['payload'])
                    try:
                        message = self.materialize(payload)
                    except SnapshotChanged:
                        # Never publishable again: fail the job visibly instead of retrying this row forever.
                        job_id = UUID(payload['job_id'])
                        await connection.execute("UPDATE replay_jobs SET status='failed',error='Snapshot changed',updated_at=now() WHERE id=$1 AND status IN ('running','paused')",job_id)
                        await connection.execute("UPDATE replay_batches SET status='failed' WHERE id=$1 AND created_at=$2",row['id'],row['created_at'])
                    else:
                        await publish('corpus.store', message)
                    # (id, created_at) is the partitioned primary key: the update touches one partition.
                    await connection.execute('UPDATE replay_outbox SET sent=true WHERE id=$1 AND created_at=$2',row['id'],row['created_at'])
                return len(rows)

    async def complete(self, result):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                job_id, batch_id = UUID(result['job_id']), UUID(result['batch_id'])
                job = await connection.fetchrow('SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE',job_id)
                if not job:
                    raise ValueError('Unknown completion batch')
                # A batch is never older than its job: created_at >= job.created_at prunes older partitions.
                batch = await connection.fetchrow('SELECT * FROM replay_batches WHERE id=$1 AND job_id=$2 AND created_at>=$3 FOR UPDATE',
                    batch_id,job_id,job['created_at'])
                if not batch:
                    raise ValueError('Unknown completion batch')
                if batch['status'] != 'pending':
                    return
                if result.get('error'):
                    await connection.execute("UPDATE replay_batches SET status='failed' WHERE id=$1 AND created_at=$2",batch_id,batch['created_at'])
                    await connection.execute("UPDATE replay_jobs SET status='failed',error=$2,updated_at=now() WHERE id=$1",job_id,result['error'][:1000])
                    return
                counts = [result[k] for k in ('inserted','duplicates','rejected')]
                if any(not isinstance(v,int) or v<0 for v in counts) or sum(counts)!=batch['end_offset']-batch['start_offset'] or result['checkpoint']!=batch['end_offset']:
                    raise ValueError('Invalid completion counts')
                await connection.execute("UPDATE replay_batches SET status='completed' WHERE id=$1 AND created_at=$2",batch_id,batch['created_at'])
                checkpoint = await connection.fetchval("SELECT min(start_offset) FROM replay_batches WHERE job_id=$1 AND created_at>=$2 AND status!='completed'",
                    job_id,job['created_at'])
                checkpoint = job['produced'] if checkpoint is None else checkpoint
                status = 'completed' if checkpoint==job['total'] else job['status']
                await connection.execute('UPDATE replay_jobs SET inserted=inserted+$2,duplicates=duplicates+$3,rejected=rejected+$4,checkpoint=$5,status=$6,updated_at=now() WHERE id=$1',
                    job_id,*counts,checkpoint,status)
                logging.getLogger(__name__).info('Completed batch=%s job=%s checkpoint=%s status=%s', batch_id, job_id, checkpoint, status)
