"""Operator console for the document store (stop or pause writers as described in docs/stages9-12-runtime.md).

    python -m content_service.manage stats
    python -m content_service.manage verify --job UUID --created-at ISO --confirmed N [--produced M] [--strategy ordered|random]
    python -m content_service.manage purge [--percent P | --limit N | --job UUID --created-at ISO --produced M] [--dry-run] --yes
    python -m content_service.manage reset [--lean-indexes] --yes
    python -m content_service.manage compact

`purge` deletes only generated `load-cs` documents; without a size it deletes all of them. `reset` drops the whole
corpus including the factual snapshots (import them again afterwards). `verify` exits with 1 if anything is missing.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from uuid import UUID

from pymongo import AsyncMongoClient

from content_service.infrastructure.database.corpus_maintenance import CorpusMaintenance, LoadJob


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('stats')
    commands.add_parser('compact')
    reset = commands.add_parser('reset')
    reset.add_argument('--yes', action='store_true')
    reset.add_argument('--lean-indexes', action='store_true', help='team/tournament/date indexes without load-cs')
    verify = commands.add_parser('verify')
    purge = commands.add_parser('purge')
    for command, required in ((verify, True), (purge, False)):
        command.add_argument('--job', type=UUID, required=required)
        command.add_argument('--created-at', type=datetime.fromisoformat, required=required)
        command.add_argument('--strategy', choices=('ordered', 'random'), default='ordered')
        command.add_argument('--produced', type=int, default=0)
    verify.add_argument('--confirmed', type=int, required=True)
    purge.add_argument('--percent', type=float)
    purge.add_argument('--limit', type=int)
    purge.add_argument('--pause-ms', type=float, default=0)
    purge.add_argument('--dry-run', action='store_true')
    purge.add_argument('--yes', action='store_true')
    return parser


async def run(options, maintenance: CorpusMaintenance) -> dict:
    if options.command == 'stats':
        return await maintenance.stats()
    if options.command == 'compact':
        return {'compacted': await maintenance.compact()}
    if options.command == 'reset':
        return await maintenance.reset(lean_indexes=options.lean_indexes)
    job = None
    if options.job:
        if options.created_at is None or options.created_at.tzinfo is None:
            raise ValueError('--created-at with a time zone is required with --job')
        job = LoadJob(options.job, options.created_at, options.strategy)
    if options.command == 'verify':
        return await maintenance.verify(job, options.confirmed, max(options.produced, options.confirmed))

    def progress(deleted, target):
        print(f'deleted {deleted}/{target}', file=sys.stderr, flush=True)
    return await maintenance.purge(percent=options.percent, limit=options.limit, job=job, produced=options.produced,
                                   dry_run=options.dry_run, pause=options.pause_ms / 1000, progress=progress)


async def main(arguments=None) -> int:
    parser = build_parser()
    options = parser.parse_args(arguments)
    if options.command in ('purge', 'reset') and not options.yes and not getattr(options, 'dry_run', False):
        parser.error(f'{options.command} deletes documents: repeat with --yes (or use --dry-run with purge)')
    client = AsyncMongoClient(os.environ['MONGO_URL'], serverSelectionTimeoutMS=5000, tz_aware=True)
    try:
        result = await run(options, CorpusMaintenance(client))
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        await client.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('ok', True) else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
