"""Unit tests of replay partitioning helpers and retention decisions (no database needed)."""
import asyncio
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

import pytest

from ingestion_service.infrastructure.database import partitioning as p

NOW = datetime(2026, 11, 19, 15, 30, tzinfo=timezone.utc)


def test_names_bounds_and_parsing():
    day = date(2026, 11, 19)
    assert p.partition_name('replay_outbox', day) == 'replay_outbox_p20261119'
    assert p.parse_partition_day('replay_batches_p20261119') == day
    assert p.parse_partition_day('replay_batches_default') is None
    assert p.parse_partition_day('other_p20261119') is None
    start, end = p.day_bounds(day)
    assert start == datetime(2026, 11, 19, tzinfo=timezone.utc) and end - start == timedelta(days=1)
    assert p.bounds_clause(day) == "FOR VALUES FROM ('2026-11-19T00:00:00+00:00') TO ('2026-11-20T00:00:00+00:00')"
    with pytest.raises(ValueError):
        p.partition_name('replay_jobs', day)


def test_days_are_utc_and_include_ahead():
    kyiv_evening = datetime(2026, 11, 20, 1, 0, tzinfo=timezone(timedelta(hours=2)))  # 23:00 UTC on the 19th
    assert p.utc_day(kyiv_evening) == date(2026, 11, 19)
    assert p.days_to_ensure(NOW, 1) == [date(2026, 11, 19), date(2026, 11, 20)]
    assert p.days_to_ensure(NOW, 0) == [date(2026, 11, 19)]
    with pytest.raises(ValueError):
        p.utc_day(datetime(2026, 11, 19))


def test_expiry_uses_end_of_day():
    # With a 7-day TTL a day expires once its end (next midnight) is at least 7 days in the past.
    assert p.is_expired(date(2026, 11, 11), NOW, 7)
    assert not p.is_expired(date(2026, 11, 12), NOW, 7)  # ends 11-13 00:00, only 6d15h ago
    assert not p.is_expired(date(2026, 11, 19), NOW, 7)


def test_policy_validation_and_env():
    policy = p.PartitionPolicy.from_env({'REPLAY_PARTITION_RETENTION_DAYS': '3', 'REPLAY_PARTITION_AHEAD_DAYS': '2'})
    assert (policy.retention_days, policy.ahead_days, policy.interval_seconds) == (3, 2, 3600)
    for bad in ({'retention_days': 0}, {'ahead_days': -1}, {'interval_seconds': 0}):
        with pytest.raises(ValueError):
            p.PartitionPolicy(**bad)


class FakeConnection:
    """Answers the catalog/count queries of partitioning.py from an in-memory model."""

    def __init__(self, partitions, unsent=(), pending=(), default_rows=None):
        self.partitions = set(partitions)
        self.unsent, self.pending = set(unsent), set(pending)
        self.default_rows = default_rows or {}
        self.statements = []

    @asynccontextmanager
    async def transaction(self):
        yield

    async def execute(self, sql, *args, **kwargs):
        self.statements.append(sql)
        if match := re.match(r'DROP TABLE (\w+)', sql):
            self.partitions.discard(match.group(1))
        elif match := re.match(r'CREATE TABLE (\w+) PARTITION OF', sql):
            self.partitions.add(match.group(1))

    async def fetch(self, sql, *args, **kwargs):
        if 'FROM pg_inherits' in sql:
            return [{'parent': name.rsplit('_p', 1)[0], 'name': name, 'bound': '', 'bytes': 8192}
                    for name in sorted(self.partitions)]
        if match := re.search(r'FROM (\w+)_default', sql):
            return [{'day': day} for day in self.default_rows.get(match.group(1), [])]
        raise AssertionError(sql)

    async def fetchval(self, sql, *args, **kwargs):
        if 'to_regclass($1) IS NOT NULL' in sql:
            return args[0] in self.partitions
        if 'pg_total_relation_size' in sql:
            return 8192
        if match := re.search(r'FROM (\w+) WHERE NOT sent', sql):
            return int(match.group(1) in self.unsent)
        if match := re.search(r"FROM (\w+) WHERE status = 'pending'", sql):
            return int(match.group(1) in self.pending)
        if re.search(r'FROM (\w+)_default WHERE created_at', sql):
            return 0
        if sql.startswith('SELECT count(*) FROM'):
            return 1
        raise AssertionError(sql)


def day_pair(day):
    return [p.partition_name(parent, day) for parent in p.PARENTS]


def test_retention_drops_old_days_in_fk_order_and_keeps_blocked_ones():
    old, blocked_unsent, blocked_pending, recent = (date(2026, 11, 1), date(2026, 11, 2), date(2026, 11, 3), date(2026, 11, 18))
    connection = FakeConnection(day_pair(old) + day_pair(blocked_unsent) + day_pair(blocked_pending) + day_pair(recent),
                                unsent={p.partition_name('replay_outbox', blocked_unsent)},
                                pending={p.partition_name('replay_batches', blocked_pending)})
    log = asyncio.run(p.drop_expired_partitions(connection, NOW, 7))
    actions = {entry['day']: entry['action'] for entry in log}
    assert actions == {'2026-11-01': 'dropped', '2026-11-02': 'skipped', '2026-11-03': 'skipped'}
    assert set(day_pair(old)).isdisjoint(connection.partitions)
    assert set(day_pair(recent) + day_pair(blocked_unsent) + day_pair(blocked_pending)) <= connection.partitions
    ddl = [s for s in connection.statements if s.startswith(('DROP', 'ALTER'))]
    assert ddl == ['DROP TABLE replay_outbox_p20261101',
                   'ALTER TABLE replay_batches DETACH PARTITION replay_batches_p20261101',
                   'DROP TABLE replay_batches_p20261101']
    assert any('LOCK TABLE replay_batches, replay_outbox' in s for s in connection.statements)


def test_dry_run_changes_nothing():
    connection = FakeConnection(day_pair(date(2026, 11, 1)))
    log = asyncio.run(p.drop_expired_partitions(connection, NOW, 7, dry_run=True))
    assert [entry['action'] for entry in log] == ['would_drop']
    assert not [s for s in connection.statements if s.startswith(('DROP', 'ALTER', 'LOCK'))]


def test_ensure_creates_current_next_and_stranded_default_days():
    stranded = date(2026, 11, 25)
    connection = FakeConnection(day_pair(date(2026, 11, 19)), default_rows={'replay_batches': [stranded]})
    created = asyncio.run(p.ensure_partitions(connection, NOW, 1))
    assert created == ['2026-11-20', '2026-11-25']
    assert set(day_pair(date(2026, 11, 20)) + day_pair(stranded)) <= connection.partitions
    assert asyncio.run(p.ensure_partitions(connection, NOW, 1)) == []  # idempotent
