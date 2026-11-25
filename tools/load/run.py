"""High-load measurement: runs one scenario against a stand and samples it every second.

Runs inside the Compose network (service `loadtest`), because it reads `serverStatus` of every shard directly:

    docker compose -f deploy/docker-compose.sharded.yml --env-file .env run --rm loadtest \
        python tools/load/run.py tools/load/scenarios/E1-ordered.yaml --out /out/E1-ordered

Writes samples.csv (one row per second), shards.csv (one row per shard and second), probe.csv (read latency) and
summary.json. The speed is the change of the committed document counters in MongoDB, not the broker rate.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
import yaml
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from content_service.infrastructure.database.corpus_maintenance import CorpusMaintenance, LoadJob
from tools.load.metrics import change, percentile, phases, shard_metrics, slowdown

STEPS = {'run': float, 'pause': float, 'purge_percent': float, 'rate': int, 'restart_shards': bool}
DRAIN_SECONDS = 180


def load_scenario(path: Path) -> dict:
    scenario = yaml.safe_load(path.read_text(encoding='utf-8'))
    for step in scenario['steps']:
        if len(step) != 1 or next(iter(step)) not in STEPS:
            raise ValueError(f'Unknown scenario step {step}; expected one of {tuple(STEPS)}')
    scenario.setdefault('snapshot', 'load-cs')
    scenario.setdefault('rate', 0)
    scenario.setdefault('probe_rps', 0)
    return scenario


class Run:
    def __init__(self, scenario: dict, out: Path, options):
        self.scenario, self.out, self.options = scenario, out, options
        self.client = AsyncMongoClient(options.mongo_url, serverSelectionTimeoutMS=3000, tz_aware=True)
        self.maintenance = CorpusMaintenance(self.client)
        self.http = httpx.AsyncClient(timeout=20, headers={'Authorization': 'Bearer ' + os.environ.get('OPERATOR_TOKEN', '')})
        self.direct, self.previous, self.sizes = {}, {}, {}
        self.samples, self.shard_rows, self.probes, self.events = [], [], [], []
        self.phase, self.writing, self.job, self.started = 'setup', False, None, time.perf_counter()

    def now(self) -> float:
        return round(time.perf_counter() - self.started, 2)

    def event(self, kind: str, /, **details):
        self.events.append({'t': self.now(), 'event': kind, **details})
        print(json.dumps(self.events[-1]), flush=True)

    async def api(self, method: str, path: str, **options) -> dict:
        response = await self.http.request(method, f'{self.options.ingestion_url}/api/v1{path}', **options)
        response.raise_for_status()
        return response.json()

    # --------------------------------------------------------------- sampling

    async def connect_shards(self):
        if (await self.client.admin.command('hello')).get('msg') == 'isdbgrid':
            for shard in (await self.client.admin.command('listShards'))['shards']:
                address = shard['host'].split('/', 1)[1].split(',')[0]
                self.direct[shard['_id']] = AsyncMongoClient(f'mongodb://{address}/', directConnection=True, serverSelectionTimeoutMS=800)
        else:
            self.direct['single'] = self.client

    async def shard_sample(self, name: str, moment: float) -> dict:
        try:
            current = shard_metrics(await self.direct[name].admin.command('serverStatus'))
        except PyMongoError:
            self.previous.pop(name, None)
            return {'t': moment, 'shard': name, 'up': 0}
        before = self.previous.get(name)
        self.previous[name] = (moment, current)
        return {'t': moment, 'shard': name, 'up': 1, **change(before and before[1], current, moment - before[0] if before else 0),
                **self.sizes.get(name, {})}

    async def sample_sizes(self):
        while True:
            try:
                for row in (await self.maintenance.stats(exact=False))['shards']:
                    self.sizes[row['shard']] = {key: row[key] for key in ('storage_bytes', 'index_bytes')}
            except PyMongoError:
                pass
            await asyncio.sleep(10)

    async def sample(self):
        last_stored = last_moment = None
        while True:
            moment = self.now()
            row = {'t': moment, 'phase': self.phase, 'writing': int(self.writing), 'stored': None, 'docs_per_s': None}
            try:
                async with asyncio.timeout(3):
                    row['stored'] = await self.maintenance.stored_load_documents()
                if last_stored is not None and moment > last_moment:
                    row['docs_per_s'] = round((row['stored'] - last_stored) / (moment - last_moment), 1)
                last_stored, last_moment = row['stored'], moment
            except (PyMongoError, TimeoutError):
                row['docs_per_s'] = 0.0 if self.writing else None  # the store answers nothing: no committed documents
            if self.job:
                try:
                    state = await self.api('GET', f'/replays/{self.job}')
                    row.update(produced=state['attempted'], inserted=state['inserted'], backlog=state['backlog'], status=state['status'])
                except httpx.HTTPError:
                    pass
            self.samples.append(row)
            self.shard_rows += await asyncio.gather(*(self.shard_sample(name, moment) for name in self.direct))
            await asyncio.sleep(max(0, 1 - (self.now() - moment)))

    async def probe(self):
        """Fixed read rate during the whole run: how the system answers while it is being written to."""
        paths, number = self.scenario.get('probe_paths') or ['/documents', '/corpus/statistics'], 0

        async def one(path):
            begun, status = time.perf_counter(), 0
            try:
                status = (await self.http.get(f'{self.options.content_url}/api/v1{path}')).status_code
            except httpx.HTTPError:
                pass
            self.probes.append({'t': self.now(), 'phase': self.phase, 'path': path, 'status': status,
                                'ms': round(1000 * (time.perf_counter() - begun), 1)})
        tasks = set()
        while True:
            task = asyncio.create_task(one(paths[number % len(paths)]))
            tasks.add(task)
            task.add_done_callback(tasks.discard)
            number += 1
            await asyncio.sleep(1 / self.scenario['probe_rps'])

    # --------------------------------------------------------------- steps

    async def drained(self):
        for _ in range(DRAIN_SECONDS):
            if (await self.api('GET', f'/replays/{self.job}'))['backlog'] == 0:
                return True
            await asyncio.sleep(1)
        return False

    async def pause(self):
        await self.api('POST', f'/replays/{self.job}/pause')
        drained = await self.drained()
        self.writing = False
        self.event('paused', drained=drained)

    async def resume(self):
        await self.api('POST', f'/replays/{self.job}/resume')
        self.writing = True
        self.event('resumed')

    async def restart_shards(self):
        """`restart: unless-stopped` starts the containers again: the caches are cold afterwards."""
        for name, client in self.direct.items():
            try:
                await client.admin.command('shutdown', force=True)
            except PyMongoError:
                pass  # the connection closes before the reply
            self.event('shutdown', shard=name)
        await asyncio.sleep(3)
        async with asyncio.timeout(180):
            while True:
                try:
                    for client in self.direct.values():
                        if not (await client.admin.command('hello')).get('isWritablePrimary'):
                            raise PyMongoError('not primary yet')
                    await self.maintenance.stored_load_documents()
                    break
                except PyMongoError:
                    await asyncio.sleep(1)
        self.event('shards_restarted')

    async def step(self, number: int, kind: str, value):
        self.phase = f'{number}-{kind}'
        if kind == 'run':
            end = self.now() + value
            while self.now() < end:
                state = await self.api('GET', f'/replays/{self.job}')
                if state['status'] != 'running':
                    raise RuntimeError(f"Job is {state['status']}: {state.get('error')}")
                await asyncio.sleep(min(5, max(.1, end - self.now())))
        elif kind == 'rate':
            await self.api('PATCH', f'/replays/{self.job}/rate', json={'target_rate': value})
            self.event('rate', value=value)
        else:
            await self.pause()
            if kind == 'pause':
                await asyncio.sleep(value)
            elif kind == 'purge_percent':
                self.event('purged', **await self.maintenance.purge(percent=value))
            elif kind == 'restart_shards':
                await self.restart_shards()
            await self.resume()

    async def execute(self) -> dict:
        await self.connect_shards()
        self.event('scenario', name=self.scenario['name'], shards=sorted(self.direct))
        background = [asyncio.create_task(self.sample()), asyncio.create_task(self.sample_sizes())]
        if self.scenario['probe_rps']:
            background.append(asyncio.create_task(self.probe()))
        error = None
        try:
            job = await self.api('POST', '/replays', headers={'Idempotency-Key': str(uuid4())},
                                 json={'snapshot_id': self.scenario['snapshot'], 'target_rate': self.scenario['rate']})
            self.job, self.writing = job['id'], True
            self.event('job', id=job['id'])
            for number, entry in enumerate(self.scenario['steps'], 1):
                kind, value = next(iter(entry.items()))
                await self.step(number, kind, value)
            self.phase = 'finish'
            await self.pause()
        except Exception as exc:  # keep what was measured
            error = f'{type(exc).__name__}: {exc}'
            self.event('error', error=error)
        finally:
            if self.job:
                try:
                    job = await self.api('POST', f'/replays/{self.job}/cancel')
                except httpx.HTTPError:
                    pass
            for task in background:
                task.cancel()
            for outcome in await asyncio.gather(*background, return_exceptions=True):
                if isinstance(outcome, Exception):
                    self.event('sampling_error', error=repr(outcome))
        return await self.summary(error)

    async def summary(self, error) -> dict:
        summary = {'scenario': self.scenario, 'error': error, 'finished_at': datetime.now(timezone.utc).isoformat(),
                   'shards': sorted(self.direct), 'events': self.events, 'phases': phases(self.samples),
                   'slowdown': slowdown(self.samples)}
        for path in sorted({row['path'] for row in self.probes}):
            values = [row['ms'] for row in self.probes if row['path'] == path and row['status'] == 200]
            failed = sum(1 for row in self.probes if row['path'] == path and row['status'] != 200)
            summary.setdefault('reads', {})[path] = {'requests': len(values) + failed, 'failed': failed,
                **{f'p{int(share * 100)}_ms': percentile(values, share) for share in (.5, .95, .99)}}
        if self.job and not error and self.scenario.get('verify', True) and not any('purge_percent' in s for s in self.scenario['steps']):
            state = await self.api('GET', f'/replays/{self.job}')
            job = LoadJob(UUID(state['id']), datetime.fromisoformat(state['created_at']),
                          'random' if state['snapshot_id'] == 'load-cs-random' else 'ordered')
            summary['verify'] = await self.maintenance.verify(job, state['checkpoint'], state['attempted'])
        return summary

    def write(self, summary: dict):
        self.out.mkdir(parents=True, exist_ok=True)
        for name, rows in (('samples', self.samples), ('shards', self.shard_rows), ('probe', self.probes)):
            if rows:
                with (self.out / f'{name}.csv').open('w', newline='', encoding='utf-8') as target:
                    writer = csv.DictWriter(target, fieldnames=list(dict.fromkeys(key for row in rows for key in row)))
                    writer.writeheader()
                    writer.writerows(rows)
        (self.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    async def close(self):
        await self.http.aclose()
        for client in {*self.direct.values(), self.client}:
            await client.close()


async def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('scenario', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--mongo-url', default=os.environ.get('MONGO_URL'))
    parser.add_argument('--ingestion-url', default='http://ingestion_api:8000')
    parser.add_argument('--content-url', default='http://content_api:8000')
    options = parser.parse_args(arguments)
    run = Run(load_scenario(options.scenario), options.out, options)
    try:
        summary = await run.execute()
        run.write(summary)
    finally:
        await run.close()
    print(json.dumps({key: summary[key] for key in ('error', 'phases', 'slowdown') if key in summary}, ensure_ascii=False, indent=2))
    return 1 if summary['error'] or not summary.get('verify', {}).get('ok', True) else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
