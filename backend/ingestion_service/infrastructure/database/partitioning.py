"""Daily RANGE partitions of replay_batches/replay_outbox: migration, creation and retention.

Layout (see migrations/002_partitioning.sql):
  replay_batches  PARTITION BY RANGE (created_at) -> replay_batches_pYYYYMMDD ... + replay_batches_default
  replay_outbox   PARTITION BY RANGE (created_at) -> replay_outbox_pYYYYMMDD  ... + replay_outbox_default
Bounds are whole UTC days. A batch and its outbox row share created_at (one transaction) and a
composite FK, so the two tables always have partitions with identical bounds.

Retention drops a day only when it ended more than `retention_days` ago AND its outbox partition
has no unsent rows (sent = false) AND its batch partition has no pending batches (a late
completion must still find its batch). Order is forced by the FK: DROP the outbox partition,
DETACH the batch partition (PostgreSQL refuses to DROP a referenced partition directly), DROP it.

CLI (operator/evidence use):
  python -m ingestion_service.infrastructure.database.partitioning --report
  python -m ingestion_service.infrastructure.database.partitioning --cleanup [--retention-days N]
  python -m ingestion_service.infrastructure.database.partitioning --cleanup --dry-run --now 2026-12-01T00:00:00+00:00
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)

PARENTS = ('replay_batches', 'replay_outbox')  # creation order: referenced table first
MIGRATION_LOCK = 912001  # same key as PostgresReplayStore.initialize
MAINTENANCE_LOCK = 912002
MIGRATION_TIMEOUT = 600  # seconds; overrides the pool's short command_timeout for bulk copy
_PARTITION = re.compile(r'^(replay_batches|replay_outbox)_p(\d{8})$')
_LEGACY_INDEX_SUFFIX = '_legacy'


@dataclass(frozen=True)
class PartitionPolicy:
    ahead_days: int = 1          # today + N following days are created in advance
    retention_days: int = 7      # a day partition is dropped once it ended more than N days ago
    interval_seconds: int = 3600  # background maintenance period in the worker
    lock_timeout_ms: int = 5000   # DROP waits at most this long for running outbox transactions

    def __post_init__(self):
        if self.ahead_days < 0 or self.retention_days < 1 or self.interval_seconds < 1 or self.lock_timeout_ms < 1:
            raise ValueError('Invalid partition policy')

    @classmethod
    def from_env(cls, env=os.environ):
        return cls(ahead_days=int(env.get('REPLAY_PARTITION_AHEAD_DAYS', 1)),
                   retention_days=int(env.get('REPLAY_PARTITION_RETENTION_DAYS', 7)),
                   interval_seconds=int(env.get('REPLAY_PARTITION_MAINTENANCE_SECONDS', 3600)),
                   lock_timeout_ms=int(env.get('REPLAY_PARTITION_LOCK_TIMEOUT_MS', 5000)))


# ---------------------------------------------------------------- pure helpers (unit-tested)

def utc_day(moment: datetime) -> date:
    if moment.tzinfo is None:
        raise ValueError('Timezone-aware datetime required')
    return moment.astimezone(timezone.utc).date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def partition_name(parent: str, day: date) -> str:
    if parent not in PARENTS:
        raise ValueError(f'Unknown partitioned table {parent}')
    return f'{parent}_p{day:%Y%m%d}'


def parse_partition_day(name: str) -> date | None:
    match = _PARTITION.match(name)
    return datetime.strptime(match.group(2), '%Y%m%d').date() if match else None


def days_to_ensure(now: datetime, ahead_days: int) -> list[date]:
    today = utc_day(now)
    return [today + timedelta(days=offset) for offset in range(ahead_days + 1)]


def is_expired(day: date, now: datetime, retention_days: int) -> bool:
    """True when the whole day ended at least `retention_days` before `now`."""
    return day_bounds(day)[1] <= now - timedelta(days=retention_days)


def bounds_clause(day: date) -> str:
    start, end = day_bounds(day)
    return f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}')"


# ---------------------------------------------------------------- migration of legacy heap tables

async def _relkind(connection, table):
    return await connection.fetchval(
        "SELECT c.relkind::text FROM pg_class c WHERE c.oid = to_regclass($1)", table)


async def detach_legacy(connection) -> bool:
    """Rename pre-partitioning heap tables (and their indexes) to *_legacy. Returns True if found."""
    kinds = {table: await _relkind(connection, table) for table in PARENTS}
    legacy = [table for table, kind in kinds.items() if kind == 'r']
    if not legacy:
        return False
    if len(legacy) != len(PARENTS):
        raise RuntimeError(f'Inconsistent replay schema: {kinds}')
    await connection.execute('LOCK TABLE replay_outbox, replay_batches IN ACCESS EXCLUSIVE MODE')
    for table in PARENTS:
        await connection.execute(f'ALTER TABLE {table} RENAME TO {table}_legacy')
        indexes = await connection.fetch(
            """SELECT i.relname FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid
               WHERE x.indrelid = to_regclass($1)""", f'{table}_legacy')
        for row in indexes:  # index names are schema-wide; free them for the partitioned tables
            await connection.execute(f'ALTER INDEX "{row["relname"]}" RENAME TO "{row["relname"]}{_LEGACY_INDEX_SUFFIX}"')
    log.info('Renamed legacy replay tables for partitioning migration')
    return True


_LEGACY_BATCHES = """FROM replay_batches_legacy b
    LEFT JOIN replay_outbox_legacy o ON o.id = b.id
    JOIN replay_jobs j ON j.id = b.job_id"""


async def copy_legacy(connection) -> dict:
    """Copy *_legacy rows into the partitioned tables, verify counts and drop the legacy tables.

    Legacy replay_batches had no created_at: it is taken from the batch's outbox row (both were
    written in one transaction), falling back to the job creation time.
    """
    created_at = 'COALESCE(o.created_at, j.created_at)'
    days = [row['day'] for row in await connection.fetch(
        f"SELECT DISTINCT ({created_at} AT TIME ZONE 'UTC')::date AS day {_LEGACY_BATCHES} ORDER BY 1",
        timeout=MIGRATION_TIMEOUT)]
    for day in days:
        await create_day(connection, day)
    batches = await connection.execute(
        f"""INSERT INTO replay_batches (id, job_id, start_offset, end_offset, status, created_at)
            SELECT b.id, b.job_id, b.start_offset, b.end_offset, b.status, {created_at} {_LEGACY_BATCHES}""",
        timeout=MIGRATION_TIMEOUT)
    outbox = await connection.execute(
        """INSERT INTO replay_outbox (id, payload, sent, created_at)
           SELECT id, payload, sent, created_at FROM replay_outbox_legacy""", timeout=MIGRATION_TIMEOUT)
    copied = {'replay_batches': int(batches.split()[-1]), 'replay_outbox': int(outbox.split()[-1])}
    expected = {table: await connection.fetchval(f'SELECT count(*) FROM {table}_legacy') for table in PARENTS}
    if copied != expected:
        raise RuntimeError(f'Partitioning migration count mismatch: copied={copied} expected={expected}')
    await connection.execute('DROP TABLE replay_outbox_legacy')
    await connection.execute('DROP TABLE replay_batches_legacy')
    log.info('Migrated legacy replay rows into partitions: %s days=%s', copied, [d.isoformat() for d in days])
    return {'rows': copied, 'days': [d.isoformat() for d in days]}


async def migrate(connection, sql: str, now: datetime, ahead_days: int) -> dict:
    """Idempotent; must run inside a transaction holding MIGRATION_LOCK."""
    legacy = await detach_legacy(connection)
    await connection.execute(sql)
    report = {'converted': legacy}
    if legacy:
        report['legacy'] = await copy_legacy(connection)
    report['created'] = await ensure_partitions(connection, now, ahead_days)
    return report


def migration_sql() -> str:
    return Path(__file__).with_name('migrations').joinpath('002_partitioning.sql').read_text(encoding='utf-8')


# ---------------------------------------------------------------- partition creation

async def _exists(connection, name) -> bool:
    return await connection.fetchval('SELECT to_regclass($1) IS NOT NULL', name)


async def create_day(connection, day: date) -> bool:
    """Create the day's partitions of both tables; rows stranded in DEFAULT are moved in.

    PostgreSQL refuses CREATE ... PARTITION OF when the DEFAULT partition already holds rows of
    the new range, so such rows are copied into a standalone table that is then ATTACHed.
    """
    missing = [parent for parent in PARENTS if not await _exists(connection, partition_name(parent, day))]
    if not missing:
        return False
    start, end = day_bounds(day)
    rescue = []
    for parent in missing:
        stranded = await connection.fetchval(
            f'SELECT count(*) FROM {parent}_default WHERE created_at >= $1 AND created_at < $2', start, end)
        if stranded:
            rescue.append((parent, stranded))
        else:
            await connection.execute(f'CREATE TABLE {partition_name(parent, day)} PARTITION OF {parent} {bounds_clause(day)}')
    for parent, _ in rescue:
        name = partition_name(parent, day)
        await connection.execute(f'CREATE TABLE {name} (LIKE {parent} INCLUDING DEFAULTS)')
        await connection.execute(f'INSERT INTO {name} SELECT * FROM {parent}_default WHERE created_at >= $1 AND created_at < $2',
                                 start, end, timeout=MIGRATION_TIMEOUT)
    for parent, _ in reversed(rescue):  # referencing outbox rows first, then batches
        await connection.execute(f'DELETE FROM {parent}_default WHERE created_at >= $1 AND created_at < $2', start, end)
    for parent, stranded in rescue:
        await connection.execute(f'ALTER TABLE {parent} ATTACH PARTITION {partition_name(parent, day)} {bounds_clause(day)}',
                                 timeout=MIGRATION_TIMEOUT)
        log.warning('Moved %s rows of %s from %s_default into %s', stranded, day, parent, partition_name(parent, day))
    log.info('Created partitions for %s: %s', day, [partition_name(parent, day) for parent in missing])
    return True


async def ensure_partitions(connection, now: datetime, ahead_days: int) -> list[str]:
    """Create partitions for today..today+ahead and for every day that has rows in DEFAULT."""
    days = set(days_to_ensure(now, ahead_days))
    for parent in PARENTS:
        days.update(row['day'] for row in await connection.fetch(
            f"SELECT DISTINCT (created_at AT TIME ZONE 'UTC')::date AS day FROM {parent}_default"))
    return [day.isoformat() for day in sorted(days) if await create_day(connection, day)]


# ---------------------------------------------------------------- inspection and retention

async def list_partitions(connection) -> list[dict]:
    rows = await connection.fetch(
        """SELECT parent.relname AS parent, child.relname AS name,
                  pg_get_expr(child.relpartbound, child.oid) AS bound,
                  pg_total_relation_size(child.oid) AS bytes
           FROM pg_inherits i
           JOIN pg_class parent ON parent.oid = i.inhparent
           JOIN pg_class child ON child.oid = i.inhrelid
           WHERE i.inhparent IN (to_regclass('replay_batches'), to_regclass('replay_outbox'))
           ORDER BY parent.relname, child.relname""")
    return [dict(row) for row in rows]


async def partition_report(connection) -> list[dict]:
    """Exact per-partition counts (for operators/evidence; scans every partition)."""
    report = []
    for item in await list_partitions(connection):
        name = item['name']
        if item['parent'] == 'replay_outbox':
            counts = await connection.fetchrow(f'SELECT count(*) AS rows, count(*) FILTER (WHERE NOT sent) AS unsent, '
                                               f'min(created_at) AS min_created, max(created_at) AS max_created FROM {name}')
        else:
            counts = await connection.fetchrow(f"SELECT count(*) AS rows, count(*) FILTER (WHERE status = 'pending') AS pending, "
                                               f'min(created_at) AS min_created, max(created_at) AS max_created FROM {name}')
        entry = {**item, **dict(counts)}
        for key in ('min_created', 'max_created'):
            entry[key] = entry[key].isoformat() if entry[key] else None
        report.append(entry)
    return report


async def _blockers(connection, day: date) -> tuple[int, int]:
    unsent = await connection.fetchval(f'SELECT count(*) FROM {partition_name("replay_outbox", day)} WHERE NOT sent') \
        if await _exists(connection, partition_name('replay_outbox', day)) else 0
    pending = await connection.fetchval(f"SELECT count(*) FROM {partition_name('replay_batches', day)} WHERE status = 'pending'") \
        if await _exists(connection, partition_name('replay_batches', day)) else 0
    return unsent, pending


async def drop_expired_partitions(connection, now: datetime, retention_days: int, *,
                                  dry_run: bool = False, lock_timeout_ms: int = 5000) -> list[dict]:
    """Drop day partitions older than the TTL unless they still hold unsent/pending rows.

    Each day is handled in its own short transaction. Returns one log entry per expired day.
    """
    days = sorted({day for item in await list_partitions(connection)
                   if (day := parse_partition_day(item['name'])) is not None})
    entries = []
    for day in (day for day in days if is_expired(day, now, retention_days)):
        names = {parent: partition_name(parent, day) for parent in PARENTS}
        entry = {'day': day.isoformat(), 'partitions': list(names.values())}
        try:
            async with connection.transaction():
                await connection.execute('SELECT pg_advisory_xact_lock($1)', MAINTENANCE_LOCK)
                if not dry_run:
                    await connection.execute(f"SET LOCAL lock_timeout = '{int(lock_timeout_ms)}ms'")
                    # Parents first (same order as worker transactions) to avoid lock-order deadlocks.
                    await connection.execute('LOCK TABLE replay_batches, replay_outbox IN ACCESS EXCLUSIVE MODE')
                present = {parent: name for parent, name in names.items() if await _exists(connection, name)}
                if not present:
                    continue  # already dropped by a concurrent maintainer
                entry['bytes'] = sum([await connection.fetchval('SELECT pg_total_relation_size(to_regclass($1))', name)
                                      for name in present.values()])
                entry['rows'] = {parent: await connection.fetchval(f'SELECT count(*) FROM {name}')
                                 for parent, name in present.items()}
                entry['unsent'], entry['pending'] = await _blockers(connection, day)
                if entry['unsent'] or entry['pending']:
                    entry['action'] = 'skipped'
                    entry['reason'] = 'unsent outbox rows or pending batches'
                elif dry_run:
                    entry['action'] = 'would_drop'
                else:
                    if 'replay_outbox' in present:
                        await connection.execute(f'DROP TABLE {present["replay_outbox"]}')
                    if 'replay_batches' in present:
                        await connection.execute(f'ALTER TABLE replay_batches DETACH PARTITION {present["replay_batches"]}')
                        await connection.execute(f'DROP TABLE {present["replay_batches"]}')
                    entry['action'] = 'dropped'
        except Exception as error:  # lock timeout etc.: keep the partition, retry next cycle
            entry.update(action='skipped', reason=f'{type(error).__name__}: {error}')
        level = logging.WARNING if entry['action'] == 'skipped' else logging.INFO
        log.log(level, 'Partition retention day=%s action=%s rows=%s unsent=%s pending=%s bytes=%s%s',
                entry['day'], entry['action'], entry.get('rows'), entry.get('unsent'), entry.get('pending'),
                entry.get('bytes'), f" reason={entry['reason']}" if 'reason' in entry else '')
        entries.append(entry)
    return entries


async def maintain(pool, policy: PartitionPolicy, *, now: datetime | None = None, dry_run: bool = False) -> dict:
    """One maintenance cycle: create upcoming partitions, then apply retention."""
    now = now or datetime.now(timezone.utc)
    async with pool.acquire() as connection:
        created = []
        if not dry_run:
            async with connection.transaction():
                await connection.execute('SELECT pg_advisory_xact_lock($1)', MAINTENANCE_LOCK)
                created = await ensure_partitions(connection, now, policy.ahead_days)
        retention = await drop_expired_partitions(connection, now, policy.retention_days,
                                                  dry_run=dry_run, lock_timeout_ms=policy.lock_timeout_ms)
        defaults = {parent: await connection.fetchval(f'SELECT count(*) FROM {parent}_default') for parent in PARENTS}
    if any(defaults.values()):
        log.warning('Rows remain in DEFAULT partitions: %s', defaults)
    return {'now': now.isoformat(), 'retention_days': policy.retention_days, 'dry_run': dry_run,
            'created': created, 'retention': retention, 'default_rows': defaults}


# ---------------------------------------------------------------- CLI

def _main(argv=None):
    import argparse
    import asyncio
    import json
    import asyncpg

    parser = argparse.ArgumentParser(description='Inspect and clean up replay_batches/replay_outbox partitions')
    parser.add_argument('--report', action='store_true', help='print partitions with exact row/unsent counts and sizes')
    parser.add_argument('--cleanup', action='store_true', help='create upcoming partitions and apply retention')
    parser.add_argument('--dry-run', action='store_true', help='only report what retention would drop')
    parser.add_argument('--retention-days', type=int)
    parser.add_argument('--ahead-days', type=int)
    parser.add_argument('--now', type=datetime.fromisoformat, help='simulated clock; allowed only with --dry-run')
    parser.add_argument('--database-url', default=os.getenv('INGESTION_DATABASE_URL'))
    args = parser.parse_args(argv)
    if args.now and not args.dry_run:
        parser.error('--now is allowed only together with --dry-run')
    if not args.database_url:
        parser.error('INGESTION_DATABASE_URL or --database-url is required')
    base = PartitionPolicy.from_env()
    policy = PartitionPolicy(ahead_days=base.ahead_days if args.ahead_days is None else args.ahead_days,
                             retention_days=base.retention_days if args.retention_days is None else args.retention_days,
                             interval_seconds=base.interval_seconds, lock_timeout_ms=base.lock_timeout_ms)

    async def run():
        pool = await asyncpg.create_pool(args.database_url, min_size=1, max_size=2)
        try:
            result = {}
            if args.cleanup:
                result['cleanup'] = await maintain(pool, policy, now=args.now, dry_run=args.dry_run)
            if args.report or not args.cleanup:
                async with pool.acquire() as connection:
                    result['partitions'] = await partition_report(connection)
            return result
        finally:
            await pool.close()

    print(json.dumps(asyncio.run(run()), indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    _main()
