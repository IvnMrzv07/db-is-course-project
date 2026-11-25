"""Pure functions: what is read from each shard, how runs are summarised, and what counts as a slowdown."""
from __future__ import annotations

from statistics import median

# (section, key) candidates: WiredTiger moved and renamed the checkpoint counters between 7.0 and 8.x.
CHECKPOINT = (('checkpoint', 'most recent time (msecs)'), ('transaction', 'transaction checkpoint most recent time (msecs)'))
# Cumulative counters; the sampler stores their change per second.
COUNTERS = ('inserted', 'write_micros', 'write_ops', 'pages_read', 'app_evictions', 'cache_wait_micros')
SLOWDOWN_SHARE, SLOWDOWN_HOLD, WINDOW = .8, 120, 60
MIN_PHASE_SECONDS = 5
BASELINE = (60, 300)  # minutes 2-5: after warm-up, before the data outgrows the cache


def _first(sections: dict, candidates) -> float | None:
    for section, key in candidates:
        value = (sections.get(section) or {}).get(key)
        if value is not None:
            return value
    return None


def shard_metrics(status: dict) -> dict:
    """Gauges and cumulative counters of one mongod from `serverStatus`."""
    engine = status.get('wiredTiger') or {}
    cache = engine.get('cache') or {}
    limit = cache.get('maximum bytes configured') or 0
    writes = (status.get('opLatencies') or {}).get('writes') or {}

    def share(key):
        return round(100 * cache.get(key, 0) / limit, 2) if limit else None
    return {'cache_used_pct': share('bytes currently in the cache'), 'cache_dirty_pct': share('tracked dirty bytes in the cache'),
            'checkpoint_ms': _first(engine, CHECKPOINT),
            'writers_queued': ((status.get('globalLock') or {}).get('currentQueue') or {}).get('writers', 0),
            'resident_mb': (status.get('mem') or {}).get('resident'),
            'inserted': ((status.get('metrics') or {}).get('document') or {}).get('inserted', 0),
            'write_micros': writes.get('latency', 0), 'write_ops': writes.get('ops', 0),
            'pages_read': cache.get('pages read into cache', 0),
            'app_evictions': cache.get('page evict attempts by application threads',
                                       cache.get('pages evicted by application threads', 0)),
            'cache_wait_micros': (engine.get('thread-yield') or {}).get('application thread time waiting for cache (usecs)', 0)}


def change(previous: dict | None, current: dict, seconds: float) -> dict:
    """Counters become per-second rates and an average write latency; a restarted server starts from zero again."""
    row = {key: value for key, value in current.items() if key not in COUNTERS}
    if previous is None or seconds <= 0 or any(current[key] < previous[key] for key in COUNTERS):
        return row
    delta = {key: current[key] - previous[key] for key in COUNTERS}
    row.update(inserts_per_s=round(delta['inserted'] / seconds, 1), pages_read_per_s=round(delta['pages_read'] / seconds, 1),
               app_evictions_per_s=round(delta['app_evictions'] / seconds, 1),
               cache_wait_ms_per_s=round(delta['cache_wait_micros'] / 1000 / seconds, 2),
               write_latency_ms=round(delta['write_micros'] / delta['write_ops'] / 1000, 3) if delta['write_ops'] else None)
    return row


def percentile(values, share: float) -> float | None:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))] if ordered else None


def rolling(samples, window: int = WINDOW):
    """(t, median docs/s of the last `window` seconds), only over seconds in which writing was requested."""
    points = [(row['t'], row['docs_per_s']) for row in samples if row.get('writing') and row.get('docs_per_s') is not None]
    result, start = [], 0
    for index, (moment, _) in enumerate(points):
        while points[start][0] <= moment - window:
            start += 1
        if moment - points[start][0] >= window * .8:
            result.append((moment, median(value for _, value in points[start:index + 1])))
    return result


def slowdown(samples) -> dict:
    """First moment after which the 60-second median stays below 80 % of the baseline for two minutes."""
    base = [row['docs_per_s'] for row in samples
            if row.get('writing') and row.get('docs_per_s') is not None and BASELINE[0] <= row['t'] <= BASELINE[1]]
    if len(base) < WINDOW:  # too short a run to say anything about its speed later on
        return {'baseline': None, 'started_at': None}
    baseline = median(base)
    below_since = None
    for moment, value in rolling(samples):
        if moment <= BASELINE[1]:
            continue
        if value >= SLOWDOWN_SHARE * baseline:
            below_since = None
            continue
        below_since = moment if below_since is None else below_since
        if moment - below_since >= SLOWDOWN_HOLD:
            stored = next((row['stored'] for row in samples if row['t'] >= below_since and row['stored'] is not None), None)
            return {'baseline': baseline, 'started_at': below_since, 'stored_at_start': stored}
    return {'baseline': baseline, 'started_at': None}


def phases(samples) -> list[dict]:
    """Median speed of each writing phase and of its first and last minute (pause/resume comparison)."""
    result = []
    for name in dict.fromkeys(row['phase'] for row in samples if row.get('writing')):
        rows = [row for row in samples if row['phase'] == name and row.get('writing') and row.get('docs_per_s') is not None]
        if not rows or rows[-1]['t'] - rows[0]['t'] < MIN_PHASE_SECONDS:  # pauses and restarts still write for a moment
            continue
        first, last = rows[0]['t'], rows[-1]['t']
        counts = [row['stored'] for row in rows if row.get('stored') is not None]  # absent while the store is down
        result.append({'phase': name, 'seconds': round(last - first), 'documents': counts[-1] - counts[0] if counts else 0,
                       'median': median(row['docs_per_s'] for row in rows),
                       'first_minute': median(row['docs_per_s'] for row in rows if row['t'] <= first + 60),
                       'last_minute': median(row['docs_per_s'] for row in rows if row['t'] >= last - 60)})
    return result
