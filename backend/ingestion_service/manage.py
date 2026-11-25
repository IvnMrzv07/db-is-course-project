"""Operator console for replay jobs (used by tools/ops/cs_ops.py).

    python -m ingestion_service.manage jobs
    python -m ingestion_service.manage cancel (--job UUID | --all)
    python -m ingestion_service.manage purge-jobs --yes
"""
import argparse
import asyncio
import json
import os
import sys
from uuid import UUID

import asyncpg

from ingestion_service.infrastructure.database.replay_store import Conflict, PostgresReplayStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('jobs')
    cancel = commands.add_parser('cancel')
    target = cancel.add_mutually_exclusive_group(required=True)
    target.add_argument('--job', type=UUID)
    target.add_argument('--all', action='store_true')
    purge = commands.add_parser('purge-jobs')
    purge.add_argument('--yes', action='store_true')
    return parser


async def all_jobs(store) -> list[dict]:
    jobs, page = [], 1
    while True:
        part = (await store.list_jobs(page, 100))['items']
        jobs += part
        if len(part) < 100:
            return jobs
        page += 1


async def run(options, store) -> dict:
    if options.command == 'jobs':
        fields = ('id', 'snapshot_id', 'status', 'target_rate', 'total', 'attempted', 'inserted', 'duplicates',
                  'checkpoint', 'backlog', 'created_at', 'error')
        return {'jobs': [{field: job[field] for field in fields} for job in await all_jobs(store)]}
    if options.command == 'purge-jobs':
        return {'deleted_jobs': await store.purge_jobs()}
    targets = [str(options.job)] if options.job else [job['id'] for job in await all_jobs(store) if job['status'] in ('running', 'paused')]
    return {'cancelled': [(await store.cancel_job(job_id))['id'] for job_id in targets]}


async def main(arguments=None) -> int:
    parser = build_parser()
    options = parser.parse_args(arguments)
    if options.command == 'purge-jobs' and not options.yes:
        parser.error('purge-jobs deletes the replay history: repeat with --yes')
    pool = await asyncpg.create_pool(os.environ['INGESTION_DATABASE_URL'], min_size=1, max_size=2, command_timeout=60)
    try:
        # The schema belongs to the services; the console neither migrates it nor reads prepared snapshots.
        result = await run(options, PostgresReplayStore(pool, '.'))
    except (Conflict, LookupError) as exc:
        parser.error(str(exc))
    finally:
        await pool.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
