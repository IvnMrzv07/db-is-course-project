"""High-load write path: bulk batches, counter slots, reference outbox and concurrent delivery (no services)."""
import asyncio
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pymongo.errors import (AutoReconnect, BulkWriteError, ExecutionTimeout, NotPrimaryError, OperationFailure,
                            ServerSelectionTimeoutError)

from content_service.application.ports.corpus_store import StoreUnavailable
from content_service.application.dtos.distributed_query import DistributedAggregationQuery
from content_service.application.dtos.document_query import DocumentQuery
from content_service.application.services.commands.corpus_command_service import CorpusCommandService, MAX_BATCH_DOCUMENTS
from content_service.infrastructure.database.availability import is_unavailable
from content_service.infrastructure.database.cluster_status import MongoClusterStatus, shard_view
from content_service.infrastructure.database.corpus_repository import (
    COUNTER_SLOTS, MongoCorpusRepository, counter_id, counters_by_scope)
from content_service.infrastructure.messaging.runtime_broker import Broker
from content_service.worker import dispatch_once, worker_roles
from contracts.load_ids import MAX_INDEX, load_document_id
from contracts.messages import SEARCH_INDEX_QUEUE
from ingestion_service.application.services.commands.replay_operations import ReplayOperations
from ingestion_service.infrastructure.database.replay_store import (
    PostgresReplayStore, ProductionLimits, SnapshotChanged, next_production)
from ingestion_service.infrastructure.datasets.load_generator import (
    BASE_FILE, MANIFEST_FILE, load_snapshots, prepare_load_base)
from ingestion_service.infrastructure.datasets.prepare_corpus import convert
from tests.test_corpus_runtime import Database, batch, row, stored


def documents(count):
    return [convert(row(match_id=str(index)), 'digest') for index in range(count)]


# --------------------------------------------------------------------------- Content: bulk batches

def test_duplicate_inside_one_batch_is_counted_once():
    async def scenario():
        db = Database()
        service = CorpusCommandService(MongoCorpusRepository(db))
        first, second = documents(2)
        result = await service.store({**batch(), 'documents': [first, second, copy.deepcopy(first)]})
        assert (result['inserted'], result['duplicates']) == (2, 1)
        assert len(db.source_documents.rows) == stored(db) == 2
        conflicting = copy.deepcopy(documents(3)[2])
        changed = copy.deepcopy(conflicting)
        changed['metadata']['snapshot_sha256'] = 'other'
        with pytest.raises(ValueError, match='migration required'):
            await service.store({**batch(), 'documents': [conflicting, changed]})
        assert stored(db) == 2
    asyncio.run(scenario())


def test_batch_mixes_new_and_stored_documents():
    async def scenario():
        db = Database()
        service = CorpusCommandService(MongoCorpusRepository(db))
        every = documents(10)
        assert (await service.store({**batch(), 'documents': every[:4]}))['inserted'] == 4
        result = await service.store({**batch(), 'documents': every})
        assert (result['inserted'], result['duplicates']) == (6, 4) and stored(db) == 10
        assert set(db.source_documents.rows) == {document['id'] for document in every}
    asyncio.run(scenario())


def test_batch_size_limits():
    service = CorpusCommandService(SimpleNamespace())
    for size in (0, MAX_BATCH_DOCUMENTS + 1):
        with pytest.raises(ValueError, match='batch size'):
            asyncio.run(service.store({**batch(), 'documents': [{}] * size}))


def test_counter_slots_are_stable_bounded_and_summed_with_legacy_rows():
    batches = [str(uuid4()) for _ in range(2000)]
    slots = {counter_id('kaggle-cs', identifier) for identifier in batches}
    assert len(slots) == COUNTER_SLOTS and counter_id('kaggle-cs', batches[0]) == counter_id('kaggle-cs', batches[0])
    rows = [{'_id': 'kaggle-cs', 'stored_documents': 5}, {'_id': 'kaggle-cs#01', 'stored_documents': 7},
            {'_id': 'synthetic-cs#01', 'stored_documents': 3}]
    assert counters_by_scope(rows) == {'kaggle-cs': 12, 'synthetic-cs': 3}


# --------------------------------------------------------------------------- Content: dispatcher and broker

def test_dispatch_marks_only_confirmed_rows():
    async def scenario():
        rows = [{'_id': str(n), 'payload': {'n': n}} for n in range(4)]
        rows[1]['queue'] = SEARCH_INDEX_QUEUE
        marked = []

        async def unsent(limit):
            return rows[:limit]

        async def mark_sent(confirmed):
            marked.extend(confirmed)

        async def publish(queue, payload):
            if payload['n'] == 2:
                raise ConnectionError('broker down')
        repository = SimpleNamespace(unsent=unsent, mark_sent=mark_sent)
        with pytest.raises(ConnectionError):
            await dispatch_once(repository, publish)
        assert [row['_id'] for row in marked] == ['0', '1', '3']
        assert await dispatch_once(SimpleNamespace(unsent=unsent, mark_sent=mark_sent), publish, limit=2) == 2
    asyncio.run(scenario())


def test_worker_roles():
    assert worker_roles(None) == ('consume', 'dispatch')
    assert worker_roles('dispatch') == ('dispatch',)
    for value in ('other', ' , '):
        with pytest.raises(ValueError):
            worker_roles(value)


class Message:
    def __init__(self, body, headers=None, ack_fails=False):
        self.body, self.headers, self.message_id = body, headers, 'id'
        self.state, self.ack_fails, self.processed = None, ack_fails, False

    async def ack(self):
        if self.ack_fails:
            raise ConnectionError('channel closed')
        self.state, self.processed = 'ack', True

    async def nack(self, requeue):
        self.state, self.processed = 'requeued' if requeue else 'dropped', True


class Iterator:
    def __init__(self, messages):
        self.messages = list(messages)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.messages:
            return self.messages.pop(0)
        await asyncio.sleep(3600)  # an idle queue stays open until the worker is cancelled


def broker_with(messages=(), concurrency=1):
    broker = Broker(concurrency=concurrency)
    broker.published = []

    async def get_queue(name):
        return SimpleNamespace(iterator=lambda: Iterator(messages))

    async def publish(message, routing_key, **kwargs):
        broker.published.append((routing_key, message))
    broker.consumer_channel = SimpleNamespace(get_queue=get_queue)
    broker.channel = SimpleNamespace(default_exchange=SimpleNamespace(publish=publish))
    return broker


def test_consumer_runs_batches_concurrently_and_acks_after_the_handler():
    async def scenario():
        messages = [Message(json.dumps({'n': n}).encode()) for n in range(4)]
        running, peak, release = 0, 0, asyncio.Event()

        async def handler(payload):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await release.wait()
            running -= 1
        consumer = asyncio.create_task(broker_with(messages, 4).consume('corpus.store', handler))
        await asyncio.sleep(.05)
        assert peak == 4 and all(message.state is None for message in messages)
        release.set()
        await asyncio.sleep(.05)
        assert [message.state for message in messages] == ['ack'] * 4
        consumer.cancel()
        await asyncio.gather(consumer, return_exceptions=True)
    asyncio.run(scenario())


def test_failed_ack_does_not_stop_the_consumer():
    async def scenario():
        async def handler(payload):
            pass
        broker = broker_with()
        await broker._process('corpus.store', Message(b'{}', ack_fails=True), handler, None)  # logged, redelivered by AMQP
    asyncio.run(scenario())


def test_poison_message_is_quarantined_after_five_attempts(monkeypatch):
    async def scenario():
        async def handler(payload):
            raise ValueError('invalid document')
        failures = []

        async def failed(payload, error):
            failures.append(error)
        payload = json.dumps({'job_id': str(uuid4()), 'batch_id': str(uuid4())}).encode()
        broker, message = broker_with(), Message(payload, {'attempt': 1})
        await broker._process('corpus.store', message, handler, failed)
        assert message.state == 'ack' and failures == []
        assert broker.published[0][0] == 'corpus.store' and broker.published[0][1].headers['attempt'] == 2
        broker, message = broker_with(), Message(payload, {'attempt': 4})
        await broker._process('corpus.store', message, handler, failed)
        assert broker.published[0][0] == 'corpus.store.failed' and failures == ['invalid document']
    pause = asyncio.sleep
    monkeypatch.setattr(asyncio, 'sleep', lambda seconds: pause(0))
    asyncio.run(scenario())


def test_broker_concurrency_must_be_positive():
    with pytest.raises(ValueError):
        Broker(concurrency=0)


# --------------------------------------------------------------------------- Ingestion: rates and reference outbox

def test_rates_and_batch_sizes():
    for rate in (0, 10, 5000, 100_000):
        ReplayOperations.validate_rate(rate)
    for rate in (-1, 1, 9, 100_001):
        with pytest.raises(ValueError):
            ReplayOperations.validate_rate(rate)
    limits = ProductionLimits()
    assert [limits.size_for(rate) for rate in (10, 500, 5000, 100_000, 0)] == [1, 50, 500, 500, 500]
    assert ProductionLimits.from_env({'REPLAY_BATCH_SIZE': '50', 'REPLAY_MAX_OUTSTANDING': '100'}) == ProductionLimits(50, 100)
    for values in ((0, 10), (1001, 5000), (500, 100)):
        with pytest.raises(ValueError):
            ProductionLimits(*values)


def test_pacing_does_not_accumulate_staging_time():
    start = datetime(2026, 11, 25, tzinfo=timezone.utc)
    scheduled = start
    for batch_number in range(20):  # 500 documents at 5,000/s = 0.1 s; staging each batch takes 15 ms
        now = scheduled + timedelta(milliseconds=15)
        scheduled = next_production(scheduled, now, 500, 5000)
    assert scheduled == start + timedelta(seconds=2)
    late = start + timedelta(seconds=60)
    assert next_production(start, late, 500, 5000) == late - timedelta(seconds=.9)  # bounded catch-up after a stall
    assert next_production(start, late, 500, 0) == late


def test_outbox_reference_is_rebuilt_from_the_immutable_snapshot():
    store = PostgresReplayStore(None, '.')
    records = SimpleNamespace(window=lambda job, created, start, end: list(range(100))[start:end])
    store.catalog['kaggle-cs'] = ({'jsonl_sha256': 'hash'}, records)
    job, created = str(uuid4()), '2026-11-25T10:00:00+00:00'
    reference = {'schema_version': 2, 'batch_id': 'b', 'job_id': job, 'prepared_at': created,
                 'snapshot_id': 'kaggle-cs', 'snapshot_hash': 'hash', 'start': 10, 'end': 15}
    message = store.materialize(reference)
    assert message == {'schema_version': 1, 'batch_id': 'b', 'job_id': job, 'checkpoint': 15, 'prepared_at': created,
                       'documents': [10, 11, 12, 13, 14]}
    assert store.materialize({'documents': ['legacy row']}) == {'documents': ['legacy row']}
    for change in ({'snapshot_hash': 'other'}, {'snapshot_id': 'missing'}, {'end': 101}):
        with pytest.raises(SnapshotChanged):
            store.materialize({**reference, **change})


# --------------------------------------------------------------------------- load-cs: identifiers and generator

STARTED = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
SNAPSHOT = Path(__file__).resolve().parents[1] / 'data' / 'synthetic' / 'synthetic-cs.csv.gz'


def test_ordered_load_ids_are_deterministic_increasing_and_distinct_per_job():
    job, other = UUID(int=5), UUID(int=6)
    ids = [str(load_document_id(job, STARTED, index)) for index in (0, 1, 2, 500, 10**6, MAX_INDEX)]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    assert ids[0] == str(load_document_id(job, STARTED, 0)) and UUID(ids[0]).version == 8
    assert load_document_id(job, STARTED, 0) != load_document_id(other, STARTED, 0)
    later = load_document_id(UUID(int=0), STARTED + timedelta(milliseconds=1), 0)
    assert str(later) > ids[-1]
    # 64 bits of the job identifier are not part of the ID; the API's ISO timestamp round-trips to the same value.
    assert load_document_id(job, datetime.fromisoformat(STARTED.isoformat()), 7) == load_document_id(job, STARTED, 7)


def test_random_load_ids_and_invalid_input():
    job = uuid4()
    ids = [str(load_document_id(job, STARTED, index, 'random')) for index in range(200)]
    assert len(set(ids)) == 200 and ids != sorted(ids) and UUID(ids[0]).version == 5
    for arguments in ((-1, 'ordered'), (MAX_INDEX + 1, 'ordered'), (0, 'other')):
        with pytest.raises(ValueError):
            load_document_id(job, STARTED, *arguments)


@pytest.fixture(scope='module')
def load_catalog(tmp_path_factory):
    directory = tmp_path_factory.mktemp('load')
    prepare_load_base(SNAPSHOT, directory, rows=60)
    return directory, load_snapshots(directory, 1_000_000)


def test_generated_documents_are_reproducible_unique_and_consistent(load_catalog):
    _, catalog = load_catalog
    manifest, records = catalog['load-cs']
    job = uuid4()
    first = records.window(job, STARTED, 0, 180)
    assert first == records.window(job, STARTED, 0, 180) and first[60:120] == records.window(job, STARTED, 60, 120)
    assert len(records) == manifest['accepted'] == 1_000_000 and manifest['is_synthetic']
    assert len({d['id'] for d in first}) == len({d['source_id'] for d in first}) == 180
    assert [d['id'] for d in first] == sorted(d['id'] for d in first)
    # Rows with player statistics never repeat verbatim (rows without them differ by match identity and date).
    detailed = [d['text'] for d in first if d['metadata']['players']]
    assert len(detailed) > 90 and len(set(detailed)) == len(detailed)
    for document in first:
        assert document['corpus_scope'] == 'load-cs' and document['is_synthetic'] is True
        assert document['text'].startswith('Synthetic load-test record')
        assert document['metadata']['snapshot_sha256'] == manifest['jsonl_sha256']
        for player in document['metadata']['players']:
            if player['kills'] is not None:
                assert player['kills'] >= 0 and f"{player['name']}: {float(player['kills'])} kills" in document['text']
                assert player['deaths'] is None or player['kddiff'] == player['kills'] - player['deaths']
    other = records.window(uuid4(), STARTED, 0, 180)
    assert not {d['id'] for d in first} & {d['id'] for d in other}
    random_ids = [d['id'] for d in catalog['load-cs-random'][1].window(job, STARTED, 0, 50)]
    assert random_ids != sorted(random_ids)


def test_load_base_is_verified(load_catalog, tmp_path):
    source, _ = load_catalog
    assert load_snapshots(tmp_path, 10) == {}
    for name in (BASE_FILE, MANIFEST_FILE):
        (tmp_path / name).write_bytes((source / name).read_bytes())
    (tmp_path / BASE_FILE).write_bytes((source / BASE_FILE).read_bytes() + b'{}\n')
    with pytest.raises(ValueError, match='does not match'):
        load_snapshots(tmp_path, 10)


def test_content_stores_load_documents_without_search_events(load_catalog):
    _, catalog = load_catalog
    store = PostgresReplayStore(None, '.')
    store.catalog.update(catalog)
    reference = {'schema_version': 2, 'batch_id': str(uuid4()), 'job_id': str(uuid4()), 'prepared_at': STARTED.isoformat(),
                 'snapshot_id': 'load-cs', 'snapshot_hash': catalog['load-cs'][0]['jsonl_sha256'], 'start': 0, 'end': 20}
    message = store.materialize(reference)
    assert message == store.materialize(reference)

    async def scenario():
        db = Database()
        service = CorpusCommandService(MongoCorpusRepository(db, index_events=True))
        result = await service.store(message)
        assert result['inserted'] == 20 and result['checkpoint'] == 20 and stored(db, 'load-cs') == 20
        assert [row.get('queue') for row in db.outbox.rows.values()] == [None]
        with pytest.raises(ValueError, match='Synthetic flag'):
            await service.store({**message, 'batch_id': str(uuid4()), 'documents': [{**message['documents'][0], 'is_synthetic': False}]})
    asyncio.run(scenario())


def test_load_documents_stay_out_of_default_reads():
    assert DocumentQuery().corpus_scope == 'kaggle-cs' and DocumentQuery(corpus_scope='load-cs').is_whole_scope
    assert not DocumentQuery(corpus_scope='load-cs', team='A').is_whole_scope
    with pytest.raises(ValueError):
        DistributedAggregationQuery(corpus_scope='load-cs')
    from content_service.infrastructure.database.distributed_aggregation import build_match
    from content_service.reindex import backfill_filter
    from search_service.domain.services.index_projection import CORPUS_SCOPES as SEARCHED
    assert 'load-cs' not in build_match(DistributedAggregationQuery())['corpus_scope']['$in']
    assert 'load-cs' not in backfill_filter('all')['corpus_scope']['$in'] and 'load-cs' not in SEARCHED


# --------------------------------------------------------------------------- shard outages

def bulk_error(*codes):
    return BulkWriteError({'writeErrors': [{'code': code, 'errmsg': ''} for code in codes], 'writeConcernErrors': []})


@pytest.mark.parametrize('error, expected', [
    (AutoReconnect('closed'), True), (ServerSelectionTimeoutError('no primary'), True), (NotPrimaryError('stepped down'), True),
    (OperationFailure('no host for shard2RS', 133), True), (ExecutionTimeout('operation exceeded time limit', 50), True),
    (OperationFailure('conflict', 112), True), (bulk_error(133, 133), True),
    (OperationFailure('labelled', 1, {'errorLabels': ['TransientTransactionError']}), True),
    (OperationFailure('bad value', 2), False), (OperationFailure('unauthorized', 13), False),
    (bulk_error(11000), False), (bulk_error(133, 121), False), (ValueError('invalid'), False)])
def test_unavailability_is_classified_by_cause(error, expected):
    assert is_unavailable(error) is expected


@pytest.mark.parametrize('failure, expected', [
    (AutoReconnect('closed'), StoreUnavailable), (OperationFailure('no host', 133), StoreUnavailable),
    (OperationFailure('bad value', 2), OperationFailure), (ValueError('migration required'), ValueError)])
def test_persist_batch_reports_outages_separately_from_bad_data(failure, expected):
    class FailingSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def with_transaction(self, callback, **kwargs): raise failure
    db = Database()
    db.client = SimpleNamespace(start_session=FailingSession)
    with pytest.raises(expected):
        asyncio.run(MongoCorpusRepository(db).persist_batch(batch()))


def test_hanging_commit_is_limited():
    class HangingSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def with_transaction(self, callback, **kwargs): await asyncio.sleep(60)
    db = Database()
    db.client = SimpleNamespace(start_session=HangingSession)
    with pytest.raises(StoreUnavailable, match='No commit'):
        asyncio.run(MongoCorpusRepository(db, commit_timeout=.05).persist_batch(batch()))


def test_outage_requeues_without_spending_attempts_and_backs_off(monkeypatch):
    async def scenario():
        pauses, unavailable = [], True

        async def handler(payload):
            if unavailable:
                raise StoreUnavailable('shard absent')

        async def pause(seconds):
            pauses.append(seconds)
        monkeypatch.setattr(asyncio, 'sleep', pause)
        broker = broker_with()
        messages = [Message(b'{}', {'attempt': 4}) for _ in range(6)]  # one more attempt would quarantine them
        for message in messages:
            await broker._process('corpus.store', message, handler, None)
        assert [message.state for message in messages] == ['requeued'] * 6 and broker.published == []
        assert pauses == [1, 2, 4, 5, 5, 5]
        unavailable, recovered = False, Message(b'{}', {'attempt': 4})
        await broker._process('corpus.store', recovered, handler, None)
        assert recovered.state == 'ack'
        pauses.clear()
        unavailable = True
        await broker._process('corpus.store', Message(b'{}'), handler, None)
        assert pauses == [1]  # the pause starts over after a successful batch
    asyncio.run(scenario())


def test_shard_view_needs_a_reachable_primary():
    pools = {'shard1RS': {'hosts': [{'addr': 'a', 'ok': True, 'ismaster': True}]},
             'shard2RS': {'hosts': [{'addr': 'b', 'ok': False, 'ismaster': False}, {'addr': 'c', 'ok': True, 'ismaster': False}]}}
    assert shard_view({'_id': 'shard1RS'}, pools)['available']
    assert not shard_view({'_id': 'shard2RS'}, pools)['available'] and not shard_view({'_id': 'missing'}, pools)['available']


def test_cluster_status_for_a_router_and_a_single_node():
    class Admin:
        def __init__(self, replies): self.replies = replies
        async def command(self, name): return self.replies[name]

    async def run(replies):
        async def find_one(*args): return {'_id': 'content', 'primary': 'shard2RS'}
        client = SimpleNamespace(admin=Admin(replies), config=SimpleNamespace(databases=SimpleNamespace(find_one=find_one)))
        return await MongoClusterStatus(client).status()
    up, down = {'addr': 'x', 'ok': True, 'ismaster': True}, {'addr': 'y', 'ok': False, 'ismaster': False}
    state = asyncio.run(run({'hello': {'msg': 'isdbgrid'}, 'listShards': {'shards': [{'_id': 'shard2RS'}, {'_id': 'shard1RS'}]},
                             'connPoolStats': {'replicaSets': {'shard1RS': {'hosts': [up]}, 'shard2RS': {'hosts': [down]}}}}))
    assert state['topology'] == 'sharded' and state['available'] is False
    assert [(s['id'], s['available'], s['database_primary']) for s in state['shards']] == [('shard1RS', True, False), ('shard2RS', False, True)]
    assert asyncio.run(run({'hello': {'isWritablePrimary': True}}))['topology'] == 'single'
