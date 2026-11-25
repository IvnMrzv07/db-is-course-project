"""Operator commands for a running Compose stand (standard library only; macOS, Linux and Windows).

    python tools/ops/cs_ops.py [--shards 1|3] up | stop
    python tools/ops/cs_ops.py status
    python tools/ops/cs_ops.py stats
    python tools/ops/cs_ops.py start [--snapshot load-cs] [--rate 0]      # 0 = MAX
    python tools/ops/cs_ops.py pause|resume|cancel --job UUID
    python tools/ops/cs_ops.py verify --job UUID
    python tools/ops/cs_ops.py shard stop|kill|start N
    python tools/ops/cs_ops.py purge [--percent P | --limit N | --job UUID] [--dry-run | --yes] [--compact]
    python tools/ops/cs_ops.py reset [--lean-indexes] --yes

The default stand is `cs-sharded` (three shards); `--shards 1` selects the separate one-shard project `cs-single`.
Use --file for another Compose file. OPERATOR_TOKEN comes from the environment or the --env-file. `purge` deletes only generated `load-cs` documents; `reset` empties every store of the stand.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
WORKERS = ('ingestion_worker', 'content_worker', 'content_dispatcher', 'search_worker')
QUEUES = ('corpus.store', 'corpus.completed', 'search.index')
SHARD_ACTIONS = {'stop': ('stop',), 'kill': ('kill', '-s', 'SIGKILL'), 'start': ('start',)}


class OpsError(Exception):
    pass


def read_env(path: Path) -> dict:
    values = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip()
    return values


class Stand:
    def __init__(self, file: str, env_file: str, url: str | None = None, shards: int = 3):
        self.env = {**read_env(ROOT / env_file), **os.environ}
        self.base = ['docker', 'compose', '-f', file, '--env-file', env_file]
        self.shards = shards
        if shards < 3:
            self.base += ['-p', 'cs-single']
            self.env['SHARDS'] = ' '.join(f'shard{number}' for number in range(1, shards + 1))
        self.url = (url or f"http://127.0.0.1:{self.env.get('SHARDED_HTTP_PORT', '8082')}").rstrip('/') + '/api/v1'

    def compose(self, *arguments: str, check: bool = True) -> str:
        result = subprocess.run([*self.base, *arguments], cwd=ROOT, text=True, encoding='utf-8', capture_output=True, env=self.env)
        if result.returncode and check:
            raise OpsError(f"docker compose {' '.join(arguments)} failed:\n{result.stderr.strip()[-2000:]}{result.stdout.strip()[-2000:]}")
        return result.stdout

    def manage(self, service: str, module: str, *arguments: str, check: bool = True) -> dict:
        output = self.compose('exec', '-T', service, 'python', '-m', module, *arguments, check=check)
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            raise OpsError(f'{module} {" ".join(arguments)} returned no result') from None

    def services(self) -> list[str]:
        return self.compose('config', '--services').split()

    def api(self, method: str, path: str, body: dict | None = None, headers: dict | None = None):
        request = urllib.request.Request(self.url + path, method=method, data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer ' + self.env.get('OPERATOR_TOKEN', ''), 'Content-Type': 'application/json', **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise OpsError(f'{method} {path}: HTTP {exc.code} {exc.read().decode(errors="replace")[:300]}') from exc
        except urllib.error.URLError as exc:
            raise OpsError(f'{method} {path}: {exc.reason}') from exc


def job_arguments(job: dict) -> list[str]:
    if not job['snapshot_id'].startswith('load-cs'):
        raise OpsError(f"Job {job['id']} replays {job['snapshot_id']}; only generated load jobs have recomputable IDs")
    return ['--job', job['id'], '--created-at', job['created_at'], '--strategy',
            'random' if job['snapshot_id'] == 'load-cs-random' else 'ordered', '--produced', str(job['attempted'])]


def verify(stand: Stand, job_id: str) -> dict:
    """Every document the pipeline reported as confirmed must be found by its recomputed ID."""
    job = stand.api('GET', f'/replays/{job_id}')
    report = stand.manage('content_api', 'content_service.manage', 'verify', *job_arguments(job),
                          '--confirmed', str(job['checkpoint']), check=False)
    return {'job_status': job['status'], 'inserted': job['inserted'], 'backlog': job['backlog'], **report}


def purge(stand: Stand, options) -> dict:
    arguments = ['purge']
    if options.percent is not None:
        arguments += ['--percent', str(options.percent)]
    if options.limit is not None:
        arguments += ['--limit', str(options.limit)]
    if options.job:
        arguments += job_arguments(stand.api('GET', f'/replays/{options.job}'))
    result = stand.manage('content_api', 'content_service.manage', *arguments, '--dry-run' if options.dry_run else '--yes')
    if options.compact and not options.dry_run:
        result['compact'] = stand.manage('content_api', 'content_service.manage', 'compact')['compacted']
    return result


def up(stand: Stand) -> dict:
    absent = [f'shard{number}' for number in range(stand.shards + 1, 4)]
    stand.compose('up', '--build', '-d', *(part for name in absent for part in ('--scale', f'{name}=0')))
    return {'shards': stand.shards, 'url': stand.url.removesuffix('/api/v1')}


def reset(stand: Stand, lean_indexes: bool = False) -> dict:
    """Order matters: no producer, no consumer and no queued batch may be left when the stores are emptied."""
    available = stand.services()
    workers = [name for name in WORKERS if name in available]
    result = {'cancelled': stand.manage('ingestion_api', 'ingestion_service.manage', 'cancel', '--all')['cancelled']}
    stand.compose('stop', *workers)
    try:
        for queue in QUEUES:  # a stand without search has no search.index queue
            stand.compose('exec', '-T', 'rabbitmq', 'rabbitmqctl', 'purge_queue', queue, check=False)
        result['content'] = stand.manage('content_api', 'content_service.manage', 'reset', '--yes',
                                         *(['--lean-indexes'] if lean_indexes else []))
        result['ingestion'] = stand.manage('ingestion_api', 'ingestion_service.manage', 'purge-jobs', '--yes')
        if 'search_api' in available:
            result['search'] = stand.manage('search_api', 'search_service.manage', 'recreate')
    finally:
        stand.compose('start', *workers)
    return result


def status(stand: Stand) -> dict:
    jobs = stand.api('GET', '/replays?page_size=20')['items']
    return {'cluster': stand.api('GET', '/cluster/status'), 'corpus': stand.api('GET', '/corpus/statistics'),
            'jobs': [{key: job[key] for key in ('id', 'snapshot_id', 'status', 'attempted', 'inserted', 'backlog')} for job in jobs]}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--file', default='deploy/docker-compose.sharded.yml')
    parser.add_argument('--env-file', default='.env')
    parser.add_argument('--shards', type=int, choices=(1, 3), default=3)
    parser.add_argument('--url', help='base URL of the stand, default http://127.0.0.1:${SHARDED_HTTP_PORT:-8082}')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('up', 'stop', 'status', 'stats'):
        commands.add_parser(name)
    start = commands.add_parser('start')
    start.add_argument('--snapshot', default='load-cs')
    start.add_argument('--rate', type=int, default=0)
    for name in ('pause', 'resume', 'cancel', 'verify'):
        commands.add_parser(name).add_argument('--job', required=True)
    shard = commands.add_parser('shard')
    shard.add_argument('action', choices=tuple(SHARD_ACTIONS))
    shard.add_argument('number', type=int, choices=(1, 2, 3))
    delete = commands.add_parser('purge')
    size = delete.add_mutually_exclusive_group()
    size.add_argument('--percent', type=float)
    size.add_argument('--limit', type=int)
    size.add_argument('--job')
    delete.add_argument('--dry-run', action='store_true')
    delete.add_argument('--compact', action='store_true')
    delete.add_argument('--yes', action='store_true')
    empty = commands.add_parser('reset')
    empty.add_argument('--yes', action='store_true')
    empty.add_argument('--lean-indexes', action='store_true', help='team/tournament/date indexes without load-cs')
    return parser


def execute(stand: Stand, options) -> dict:
    if options.command == 'up':
        return up(stand)
    if options.command == 'stop':
        stand.compose('stop')
        return {'stopped': True}
    if options.command == 'status':
        return status(stand)
    if options.command == 'stats':
        return stand.manage('content_api', 'content_service.manage', 'stats')
    if options.command == 'start':
        return stand.api('POST', '/replays', {'snapshot_id': options.snapshot, 'target_rate': options.rate},
                         {'Idempotency-Key': str(uuid4())})
    if options.command in ('pause', 'resume', 'cancel'):
        return stand.api('POST', f'/replays/{options.job}/{options.command}')
    if options.command == 'verify':
        return verify(stand, options.job)
    if options.command == 'shard':
        stand.compose(*SHARD_ACTIONS[options.action], f'shard{options.number}')
        return {'shard': options.number, 'action': options.action}
    if options.command == 'purge':
        return purge(stand, options)
    return reset(stand, options.lean_indexes)


def main(arguments=None) -> int:
    parser = build_parser()
    options = parser.parse_args(arguments)
    if options.command in ('purge', 'reset') and not options.yes and not getattr(options, 'dry_run', False):
        parser.error(f'{options.command} deletes data: repeat with --yes')
    try:
        result = execute(Stand(options.file, options.env_file, options.url, options.shards), options)
    except OpsError as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('ok', True) else 1


if __name__ == '__main__':
    sys.exit(main())
