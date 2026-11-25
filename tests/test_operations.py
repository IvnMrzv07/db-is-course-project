"""Operator console: argument guards and the order of destructive steps (no Docker, no databases)."""
import asyncio
from types import SimpleNamespace

import pytest

from content_service import manage as content_manage
from ingestion_service import manage as ingestion_manage
from tools.ops import cs_ops

JOB = {'id': '5b0f5a3e-4a1e-4a55-9a53-000000000001', 'snapshot_id': 'load-cs', 'status': 'completed', 'attempted': 900,
       'checkpoint': 800, 'inserted': 900, 'backlog': 0, 'created_at': '2026-11-25T12:00:00+00:00'}


class FakeStand:
    def __init__(self, services=('content_worker', 'ingestion_worker', 'content_dispatcher', 'search_worker', 'search_api'), fail=None):
        self.calls, self.available, self.fail = [], list(services), fail

    def services(self):
        return self.available

    def compose(self, *arguments, check=True):
        self.calls.append(arguments)
        return ''

    def manage(self, service, module, *arguments, check=True):
        self.calls.append((service, module, *arguments))
        if self.fail in arguments:
            raise cs_ops.OpsError('failed')
        return {'cancelled': [], 'ok': True, 'compacted': []}

    def api(self, method, path, body=None, headers=None):
        self.calls.append((method, path, body))
        return JOB


@pytest.mark.parametrize('command', [['purge'], ['reset'], ['purge', '--percent', '10']])
def test_destructive_commands_need_confirmation(command, capsys):
    with pytest.raises(SystemExit) as error:
        cs_ops.main(command)
    assert error.value.code == 2
    assert '--yes' in capsys.readouterr().err


def test_service_consoles_need_confirmation():
    for main, command in ((content_manage.main, ['purge']), (content_manage.main, ['reset']), (ingestion_manage.main, ['purge-jobs'])):
        with pytest.raises(SystemExit) as error:
            asyncio.run(main(command))
        assert error.value.code == 2


def test_reset_stops_writers_before_emptying_and_always_restarts_them():
    stand = FakeStand()
    cs_ops.reset(stand)
    names = [' '.join(call) for call in stand.calls]
    position = {key: next(i for i, name in enumerate(names) if key in name) for key in
                ('cancel --all', 'stop ', 'purge_queue corpus.store', 'content_service.manage reset', 'purge-jobs',
                 'search_service.manage recreate', 'start ')}
    assert list(position.values()) == sorted(position.values())
    workers = {'ingestion_worker', 'content_worker', 'content_dispatcher', 'search_worker'}
    assert set(stand.calls[position['stop ']][1:]) == set(stand.calls[position['start ']][1:]) == workers
    broken = FakeStand(fail='reset')
    with pytest.raises(cs_ops.OpsError):
        cs_ops.reset(broken)
    assert broken.calls[-1][0] == 'start'
    plain = FakeStand(services=('content_worker', 'ingestion_worker'))  # default stand: no search, no split dispatcher
    cs_ops.reset(plain)
    assert not any('search_service.manage' in call for call in plain.calls) and ('stop', 'ingestion_worker', 'content_worker') in plain.calls


def test_verify_and_purge_recompute_ids_from_the_job():
    stand = FakeStand()
    assert cs_ops.verify(stand, JOB['id'])['ok']
    arguments = stand.calls[-1]
    assert arguments[:3] == ('content_api', 'content_service.manage', 'verify')
    assert arguments[arguments.index('--confirmed') + 1] == '800' and arguments[arguments.index('--produced') + 1] == '900'
    assert arguments[arguments.index('--strategy') + 1] == 'ordered'
    assert cs_ops.job_arguments({**JOB, 'snapshot_id': 'load-cs-random'})[5] == 'random'
    with pytest.raises(cs_ops.OpsError):
        cs_ops.job_arguments({**JOB, 'snapshot_id': 'kaggle-cs'})
    options = cs_ops.build_parser().parse_args(['purge', '--percent', '50', '--yes', '--compact'])
    cs_ops.purge(stand, options)
    assert stand.calls[-2][2:] == ('purge', '--percent', '50.0', '--yes') and stand.calls[-1][2:] == ('compact',)
    cs_ops.purge(stand, cs_ops.build_parser().parse_args(['purge', '--dry-run', '--compact']))
    assert stand.calls[-1][2:] == ('purge', '--dry-run')


def test_shard_commands_and_environment(tmp_path):
    stand = FakeStand()
    for action, expected in (('kill', ('kill', '-s', 'SIGKILL', 'shard2')), ('start', ('start', 'shard2')), ('stop', ('stop', 'shard2'))):
        cs_ops.execute(stand, cs_ops.build_parser().parse_args(['shard', action, '2']))
        assert stand.calls[-1] == expected
    (tmp_path / '.env').write_text('# comment\nOPERATOR_TOKEN=secret\nSHARDED_HTTP_PORT=9000\n', encoding='utf-8')
    assert cs_ops.read_env(tmp_path / '.env') == {'OPERATOR_TOKEN': 'secret', 'SHARDED_HTTP_PORT': '9000'}
    assert cs_ops.read_env(tmp_path / 'missing') == {}


def test_content_console_parses_load_jobs():
    options = content_manage.build_parser().parse_args(['verify', '--job', JOB['id'], '--created-at', JOB['created_at'], '--confirmed', '5'])
    captured = {}

    async def verify(job, confirmed, produced):
        captured.update(job=job, confirmed=confirmed, produced=produced)
        return {'ok': True}
    asyncio.run(content_manage.run(options, SimpleNamespace(verify=verify)))
    assert str(captured['job'].job_id) == JOB['id'] and (captured['confirmed'], captured['produced']) == (5, 5)
    naive = content_manage.build_parser().parse_args(['verify', '--job', JOB['id'], '--created-at', '2026-11-25T12:00:00', '--confirmed', '5'])
    with pytest.raises(ValueError, match='time zone'):
        asyncio.run(content_manage.run(naive, SimpleNamespace()))


def test_one_and_three_shard_stands_use_the_same_compose_file():
    single = cs_ops.Stand('deploy/docker-compose.sharded.yml', 'missing.env', shards=1)
    assert single.env['SHARDS'] == 'shard1' and single.base[-2:] == ['-p', 'cs-single']
    full = cs_ops.Stand('deploy/docker-compose.sharded.yml', 'missing.env')
    assert 'SHARDS' not in full.env and '-p' not in full.base
    for stand, expected in ((single, ('--scale', 'shard2=0', '--scale', 'shard3=0')), (full, ())):
        calls = []
        stand.compose = lambda *arguments, calls=calls, **options: calls.append(arguments) or ''
        cs_ops.up(stand)
        assert calls == [('up', '--build', '-d', *expected)]


def test_sharded_stand_limits_memory_and_disk():
    yaml = pytest.importorskip('yaml')
    with open('deploy/docker-compose.sharded.yml', encoding='utf-8') as source:
        stand = yaml.safe_load(source)
    services = stand['services']
    databases = [name for name, service in services.items() if service.get('command', [''])[0] == 'mongod']
    assert sorted(databases) == ['cfg1', 'shard1', 'shard2', 'shard3']
    for name in databases:  # unlimited caches would together take more than the Docker VM has
        assert '--wiredTigerCacheSizeGB' in services[name]['command'] and '--oplogSize' in services[name]['command']
    roles = {name: service['environment'].get('CONTENT_ROLES') for name, service in services.items() if name.startswith('content_')}
    assert roles == {'content_api': None, 'content_worker': 'consume', 'content_dispatcher': 'dispatch'}
    for name, service in services.items():
        assert all(dependency in services for dependency in service.get('depends_on') or {})
        for volume in service.get('volumes', ()):
            source = volume.split(':')[0]
            assert source.startswith(('.', '/')) or source in stand['volumes'], (name, volume)
    # shard2 and shard3 may be scaled to zero: only the initialisation script waits for shards.
    assert not any(set(service.get('depends_on') or {}) & {'shard1', 'shard2', 'shard3'} for service in services.values())
