import hashlib
import json
import logging
from pathlib import Path
from uuid import uuid4, uuid5, UUID
from datetime import datetime, timezone, timedelta

class Conflict(Exception):
    pass

class PostgresReplayStore:
    def __init__(self, pool, data_dir):
        self.pool = pool
        self.data_dir = Path(data_dir)
        self.catalog = {}

    async def initialize(self):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute('SELECT pg_advisory_xact_lock(912001)')
                await connection.execute(Path(__file__).with_name('migrations').joinpath('001_replay.sql').read_text())
        # Explicit allowlist; clients never choose paths. Verify immutable prepared input once per process.
        manifest_path = self.data_dir / 'kaggle-cs.manifest.json'
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            raw = (self.data_dir / 'kaggle-cs.jsonl').read_bytes()
            if hashlib.sha256(raw).hexdigest() != manifest['jsonl_sha256']:
                raise ValueError('Prepared corpus checksum mismatch')
            records = [json.loads(line) for line in raw.splitlines()]
            if len(records) != manifest['accepted']:
                raise ValueError('Prepared corpus count mismatch')
            self.catalog['kaggle-cs'] = (manifest, records)

    async def snapshots(self):
        return [{'id': name, 'documents': manifest['accepted'], 'validation_rejected': manifest['rejected']}
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

    async def produce(self):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                job = await connection.fetchrow("""SELECT * FROM replay_jobs WHERE status='running' AND produced<total
                    AND next_at<=now() AND produced-inserted-duplicates-rejected<1000
                    ORDER BY next_at LIMIT 1 FOR UPDATE SKIP LOCKED""")
                if not job:
                    return False
                manifest, records = self.catalog[job['snapshot_id']]
                if manifest['jsonl_sha256'] != job['snapshot_hash']:
                    await connection.execute("UPDATE replay_jobs SET status='failed',error='Snapshot changed',updated_at=now() WHERE id=$1",job['id'])
                    return False
                size = min(100,max(1,job['target_rate']//10))
                start = job['produced']
                documents = records[start:start+size]
                end = start + len(documents)
                batch_id = uuid5(job['id'],str(start))
                payload = {'schema_version': 1, 'batch_id': str(batch_id), 'job_id': str(job['id']),
                    'checkpoint': end, 'prepared_at': job['created_at'].isoformat(), 'documents': documents}
                await connection.execute('INSERT INTO replay_batches(id,job_id,start_offset,end_offset) VALUES($1,$2,$3,$4)',batch_id,job['id'],start,end)
                await connection.execute('INSERT INTO replay_outbox(id,payload) VALUES($1,$2::jsonb)',batch_id,json.dumps(payload))
                await connection.execute('UPDATE replay_jobs SET produced=$2,next_at=$3,updated_at=now() WHERE id=$1',
                    job['id'],end,datetime.now(timezone.utc)+timedelta(seconds=len(documents)/job['target_rate']))
                logging.getLogger(__name__).debug('Staged job=%s batch=%s end=%s', job['id'], batch_id, end)
                return True

    async def complete(self, result):
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                job_id, batch_id = UUID(result['job_id']), UUID(result['batch_id'])
                job = await connection.fetchrow('SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE',job_id)
                batch = await connection.fetchrow('SELECT * FROM replay_batches WHERE id=$1 AND job_id=$2 FOR UPDATE',batch_id,job_id)
                if not job or not batch:
                    raise ValueError('Unknown completion batch')
                if batch['status'] != 'pending':
                    return
                if result.get('error'):
                    await connection.execute("UPDATE replay_batches SET status='failed' WHERE id=$1",batch_id)
                    await connection.execute("UPDATE replay_jobs SET status='failed',error=$2,updated_at=now() WHERE id=$1",job_id,result['error'][:1000])
                    return
                counts = [result[k] for k in ('inserted','duplicates','rejected')]
                if any(not isinstance(v,int) or v<0 for v in counts) or sum(counts)!=batch['end_offset']-batch['start_offset'] or result['checkpoint']!=batch['end_offset']:
                    raise ValueError('Invalid completion counts')
                await connection.execute("UPDATE replay_batches SET status='completed' WHERE id=$1",batch_id)
                checkpoint = await connection.fetchval("SELECT min(start_offset) FROM replay_batches WHERE job_id=$1 AND status!='completed'",job_id)
                checkpoint = job['produced'] if checkpoint is None else checkpoint
                status = 'completed' if checkpoint==job['total'] else job['status']
                await connection.execute('UPDATE replay_jobs SET inserted=inserted+$2,duplicates=duplicates+$3,rejected=rejected+$4,checkpoint=$5,status=$6,updated_at=now() WHERE id=$1',
                    job_id,*counts,checkpoint,status)
                logging.getLogger(__name__).info('Completed batch=%s job=%s checkpoint=%s status=%s', batch_id, job_id, checkpoint, status)
