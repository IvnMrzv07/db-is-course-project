"""Retention evidence on a real PostgreSQL in a throw-away schema (never touches `public`).

Builds the pre-partitioning heap tables with back-dated rows (12..0 days old), runs the same
migration the services run on start, then two maintenance cycles of the retention policy.
Writes a JSON report and prints the maintenance log.

  INGESTION_DATABASE_URL=postgresql://... python tools/partitioning/retention_demo.py OUT.json
"""
import asyncio
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg

from ingestion_service.infrastructure.database import partitioning
from ingestion_service.infrastructure.database.replay_store import PostgresReplayStore

SCHEMA = 'partition_retention_demo'
LEGACY_DDL = """
CREATE TABLE replay_jobs (id uuid PRIMARY KEY, idempotency_key text UNIQUE NOT NULL, request_hash text NOT NULL,
 snapshot_id text NOT NULL, snapshot_hash text NOT NULL, total integer NOT NULL, status text NOT NULL,
 target_rate integer NOT NULL, produced integer NOT NULL DEFAULT 0, checkpoint integer NOT NULL DEFAULT 0,
 inserted integer NOT NULL DEFAULT 0, duplicates integer NOT NULL DEFAULT 0, rejected integer NOT NULL DEFAULT 0,
 validation_rejected integer NOT NULL DEFAULT 0, error text, next_at timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE replay_batches (id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES replay_jobs(id),
 start_offset integer NOT NULL, end_offset integer NOT NULL, status text NOT NULL DEFAULT 'pending', UNIQUE(job_id, start_offset));
CREATE TABLE replay_outbox (id uuid PRIMARY KEY REFERENCES replay_batches(id), payload jsonb NOT NULL,
 sent boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now());
"""
# age in days -> (batches per day, batch status, outbox sent); 100 documents of ~1 KB per payload
PLAN = {12: (40, 'completed', True), 10: (40, 'completed', True), 9: (40, 'completed', False),
        8: (40, 'pending', True), 3: (40, 'completed', True), 0: (40, 'completed', True)}


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(f'{datetime.fromtimestamp(record.created, timezone.utc).isoformat()} '
                          f'{record.levelname} {record.name} {record.getMessage()}')


async def main(out):
    url = os.environ['INGESTION_DATABASE_URL']
    capture = Capture()
    logging.getLogger('ingestion_service').addHandler(capture)
    logging.getLogger('ingestion_service').setLevel(logging.INFO)
    admin = await asyncpg.connect(url)
    await admin.execute(f'DROP SCHEMA IF EXISTS {SCHEMA} CASCADE')
    await admin.execute(f'CREATE SCHEMA {SCHEMA}')
    pool = await asyncpg.create_pool(url, min_size=1, max_size=3, server_settings={'search_path': SCHEMA})
    report = {'schema': SCHEMA, 'policy': {'retention_days': 7, 'ahead_days': 1}}
    try:
        now = datetime.now(timezone.utc)
        await pool.execute(LEGACY_DDL)
        job = uuid4()
        await pool.execute("INSERT INTO replay_jobs(id,idempotency_key,request_hash,snapshot_id,snapshot_hash,total,status,target_rate,created_at)"
                           " VALUES($1,'demo','h','kaggle-cs','x',100000,'running',100,$2)", job, now - timedelta(days=13))
        payload = json.dumps({'documents': [{'n': i, 'pad': 'x' * 1000} for i in range(100)]})
        offset = 0
        for age, (count, status, sent) in PLAN.items():
            for index in range(count):
                batch = uuid4()
                # only the first row of a "blocked" day carries the blocking state
                row_status = status if index == 0 else 'completed'
                row_sent = sent if index == 0 else True
                await pool.execute('INSERT INTO replay_batches VALUES($1,$2,$3,$4,$5)', batch, job, offset, offset + 100, row_status)
                await pool.execute('INSERT INTO replay_outbox VALUES($1,$2,$3,$4)', batch, payload, row_sent,
                                   now - timedelta(days=age, minutes=index))
                offset += 100
        report['legacy_rows'] = {'batches': await pool.fetchval('SELECT count(*) FROM replay_batches'),
                                 'outbox': await pool.fetchval('SELECT count(*) FROM replay_outbox'),
                                 'outbox_bytes': await pool.fetchval("SELECT pg_total_relation_size('replay_outbox')")}
        store = PostgresReplayStore(pool, tempfile.mkdtemp(), partitioning.PartitionPolicy(retention_days=7, ahead_days=1))
        await store.initialize()
        async with pool.acquire() as connection:
            report['partitions_after_migration'] = await partitioning.partition_report(connection)
        report['cycle1_dry_run'] = await store.maintain_partitions(dry_run=True)
        report['cycle1'] = await store.maintain_partitions()
        # the blockers resolve: dispatcher sent the row, the late completion arrived
        await pool.execute('UPDATE replay_outbox SET sent = true WHERE NOT sent')
        await pool.execute("UPDATE replay_batches SET status = 'completed' WHERE status = 'pending'")
        report['cycle2'] = await store.maintain_partitions()
        report['cycle3_idempotent'] = await store.maintain_partitions()
        async with pool.acquire() as connection:
            report['partitions_final'] = await partitioning.partition_report(connection)
        report['rows_final'] = {'batches': await pool.fetchval('SELECT count(*) FROM replay_batches'),
                                'outbox': await pool.fetchval('SELECT count(*) FROM replay_outbox')}
    finally:
        await pool.close()
        await admin.execute(f'DROP SCHEMA IF EXISTS {SCHEMA} CASCADE')
        await admin.close()
    report['log'] = capture.lines
    with open(out, 'w', encoding='utf-8') as target:
        json.dump(report, target, indent=1, ensure_ascii=False, default=str)
    print('\n'.join(capture.lines))


if __name__ == '__main__':
    asyncio.run(main(sys.argv[1]))
