"""Measurement functions and scenarios (pure; the runner itself needs a stand)."""
from pathlib import Path

import pytest

from tools.load.metrics import change, percentile, phases, rolling, shard_metrics, slowdown

yaml = pytest.importorskip('yaml')
SCENARIOS = Path('tools/load/scenarios')


def samples(speeds, phase='1-run', start=0, stored=0):
    rows = []
    for offset, speed in enumerate(speeds):
        stored += speed
        rows.append({'t': start + offset, 'phase': phase, 'writing': 1, 'stored': stored, 'docs_per_s': speed})
    return rows


def test_no_slowdown_for_steady_noisy_speed():
    steady = samples([1000 + (200 if second % 7 == 0 else -100) for second in range(1500)])
    assert slowdown(steady) == {'baseline': 900, 'started_at': None}


def test_slowdown_is_reported_when_it_lasts():
    result = slowdown(samples([1000] * 900 + [700] * 600))
    assert result['baseline'] == 1000 and 900 <= result['started_at'] <= 960
    assert result['stored_at_start'] == pytest.approx(900_000, rel=.05)
    # A one-minute dip (checkpoint) is not a slowdown, a gradual fall below 80 % is.
    assert slowdown(samples([1000] * 600 + [500] * 60 + [1000] * 600))['started_at'] is None
    falling = slowdown(samples([max(400, 1000 - max(0, second - 600) // 2) for second in range(2000)]))
    assert 980 <= falling['started_at'] <= 1060


def test_slowdown_needs_a_baseline_and_ignores_pauses():
    assert slowdown(samples([1000] * 30))['baseline'] is None
    paused = [{'t': second, 'phase': '2-pause', 'writing': 0, 'stored': 600_000, 'docs_per_s': 0} for second in range(600, 900)]
    assert slowdown(samples([1000] * 600) + paused + samples([1000] * 400, '3-run', 900, 600_000))['started_at'] is None


def test_outage_rows_without_counters_do_not_break_the_summary():
    rows = samples([1000] * 400)
    rows += [{'t': 400 + n, 'phase': '1-run', 'writing': 1, 'stored': None, 'docs_per_s': 0.0} for n in range(200)]
    result = slowdown(rows)
    assert result['started_at'] is not None and result['stored_at_start'] is None
    assert phases(rows)[0]['documents'] == 399_000


def test_phases_compare_the_first_and_last_minute():
    rows = samples([1000] * 300, '1-run') + samples([600] * 300, '2-run', 300, 300_000)
    first, second = phases(rows)
    assert (first['median'], second['first_minute'], second['last_minute']) == (1000, 600, 600)
    assert phases(samples([1000] * 100 + [500] * 100))[0] | {'phase': ''} == {
        'phase': '', 'seconds': 199, 'documents': 149_000, 'median': 750, 'first_minute': 1000, 'last_minute': 500}


def test_rolling_waits_for_a_full_window():
    assert rolling(samples([10] * 30)) == [] and rolling(samples([10] * 120))[-1] == (119, 10)


def test_shard_metrics_of_both_server_generations():
    cache = {'maximum bytes configured': 1000, 'bytes currently in the cache': 800, 'tracked dirty bytes in the cache': 50,
             'pages read into cache': 7, 'page evict attempts by application threads': 3}
    status = {'wiredTiger': {'cache': cache, 'checkpoint': {'most recent time (msecs)': 64}},
              'opLatencies': {'writes': {'latency': 5000, 'ops': 10}}, 'metrics': {'document': {'inserted': 100}},
              'globalLock': {'currentQueue': {'writers': 2}}, 'mem': {'resident': 300}}
    current = shard_metrics(status)
    assert (current['cache_used_pct'], current['cache_dirty_pct'], current['checkpoint_ms'], current['app_evictions']) == (80, 5, 64, 3)
    old = shard_metrics({'wiredTiger': {'cache': {'pages evicted by application threads': 9},
                                        'transaction': {'transaction checkpoint most recent time (msecs)': 12}}})
    assert (old['checkpoint_ms'], old['app_evictions'], old['cache_used_pct']) == (12, 9, None)
    later = {**current, 'inserted': 300, 'write_micros': 9000, 'write_ops': 14, 'pages_read': 17}
    rates = change(current, later, 2)
    assert (rates['inserts_per_s'], rates['write_latency_ms'], rates['pages_read_per_s']) == (100, 1, 5)
    assert 'inserts_per_s' not in change(None, current, 0)
    assert 'inserts_per_s' not in change(later, current, 1)  # restarted server: counters began again


def test_percentile():
    assert percentile([], .5) is None and percentile([5], .99) == 5
    assert (percentile(range(100), .5), percentile(range(100), .99)) == (50, 99)


def test_scenarios_are_valid():
    from tools.load.run import load_scenario
    names = [load_scenario(path)['name'] for path in sorted(SCENARIOS.glob('*.yaml'))]
    assert names == [path.stem for path in sorted(SCENARIOS.glob('*.yaml'))] and len(names) >= 6


def test_unknown_scenario_steps_are_rejected(tmp_path):
    from tools.load.run import load_scenario
    path = tmp_path / 'x.yaml'
    path.write_text('name: x\nsteps:\n  - explode: 1\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Unknown scenario step'):
        load_scenario(path)


def test_host_thermal_state_of_both_mac_generations():
    from tools.load.host_probe import speed_limit, thermal_pressure
    assert thermal_pressure('com.apple.system.thermalpressurelevel 2\n') == 2 and thermal_pressure('') is None
    assert speed_limit('CPU_Speed_Limit \t= 80\n') == 80 and speed_limit('No thermal warning level has been recorded') is None
