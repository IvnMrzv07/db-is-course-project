"""Plan item 7: Elasticsearch full-text search.

Unit tests (no services): Content `search.index` events (transactional outbox, backfill), projection and
validation, idempotent indexing, Query DSL, response parsing, HTTP states (found/empty/degraded/error).
Opt-in stand test: RUN_SEARCH_STACK_TESTS=1 against cs-sharded (SEARCH_STAND_URL, default :8082).
"""
import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from content_service.application.services.commands.corpus_command_service import CorpusCommandService
from content_service.application.services.commands.search_index_events import index_event, indexable_document
from content_service.infrastructure.database.corpus_repository import MongoCorpusRepository
from content_service.reindex import backfill, backfill_filter
from contracts.messages import SEARCH_INDEX_EVENT_TYPE, SEARCH_INDEX_QUEUE
from search_service.application.dtos.full_text_query import FullTextQuery
from search_service.application.ports.document_index import SearchBackendUnavailable
from search_service.application.services.commands.document_indexing_service import DocumentIndexingService
from search_service.application.services.queries.full_text_search_service import FullTextSearchService
from search_service.domain.exceptions import DomainError
from search_service.domain.services.index_projection import project
from search_service.infrastructure.search.elasticsearch_documents import (
    ALIAS, INDEX_DEFINITION, ElasticsearchDocumentIndex, build_search_body, bulk_payload, parse_search_response,
    summarize_bulk)
from search_service.presentation.api.app import app as search_app
from search_service.presentation.api.controllers.full_text_search_controller import FullTextSearchController
from test_corpus_runtime import Database, batch


def source_document(**changes):
    metadata = {'document_type': 'map', 'team1': 'Natus Vincere', 'team2': 'Vitality', 'map_name': 'Mirage',
                'tournament': 'IEM Katowice 2024', 'played_at': '2024-02-10T15:00:00', 'best_of': 3,
                'template_version': '2', 'winner_team': 'Vitality',
                'players': [{'name': 's1mple (Oleksandr Kostyliev), UA', 'kills': 20},
                            {'name': 'ZywOo (Mathieu Herbaut), FR', 'kills': 25},
                            {'name': 's1mple (Oleksandr Kostyliev), UA', 'kills': 1}]}
    document = {'document_id': str(uuid4()), 'version': 1, 'title': 'Natus Vincere vs Vitality — IEM Katowice 2024 — Mirage',
                'text': 'Natus Vincere played Vitality at IEM Katowice 2024. Map: Mirage.', 'language': 'en',
                'corpus_scope': 'kaggle-cs', 'is_synthetic': False, 'source_id': '1:map:2', 'metadata': metadata}
    for key, value in changes.items():
        if key == 'metadata':
            document['metadata'] = {**metadata, **value}
        else:
            document[key] = value
    return document


def event(*documents, event_type=SEARCH_INDEX_EVENT_TYPE):
    return {'event_id': 'index:1', 'event_type': event_type, 'schema_version': 1, 'origin': 'store',
            'batch_id': '1', 'documents': list(documents)}


class MemoryIndex:
    """In-memory DocumentIndex with Elasticsearch `external_gte` semantics."""

    def __init__(self):
        self.documents, self.calls = {}, 0

    async def upsert(self, documents):
        self.calls += 1
        indexed = stale = 0
        for document in documents:
            current = self.documents.get(document['id'])
            if current and current['version'] > document['version']:
                stale += 1
            else:
                self.documents[document['id']] = document
                indexed += 1
        return {'indexed': indexed, 'stale': stale}


# ---------------------------------------------------------------- Content: event production
def test_index_event_projection_is_public_and_deterministic():
    stored = {'_id': str(uuid4()), 'version': 1, 'title': 'T', 'text': 'X', 'language': 'en', 'corpus_scope': 'kaggle-cs',
              'is_synthetic': False, 'source_id': 's', 'metadata': {'document_type': 'map'}, 'publication_status': 'published',
              'stored_at': 'internal', 'source_url': 'https://example.invalid'}
    draft = {**stored, '_id': str(uuid4()), 'publication_status': 'draft'}
    payload = index_event('batch-1', [stored, draft])
    assert payload['event_id'] == 'index:batch-1' and payload['event_type'] == SEARCH_INDEX_EVENT_TYPE
    assert [d['document_id'] for d in payload['documents']] == [stored['_id']]  # drafts are never emitted
    assert set(payload['documents'][0]) == {'document_id', 'version', 'title', 'text', 'language', 'corpus_scope',
                                            'is_synthetic', 'source_id', 'metadata'}
    assert indexable_document(draft) is None
    with pytest.raises(ValueError):
        indexable_document({'id': 'not-a-uuid'})
    json.dumps(payload)  # wire form must be JSON


def test_store_stages_index_event_in_the_same_transaction():
    async def scenario():
        db = Database()
        service = CorpusCommandService(MongoCorpusRepository(db, index_events=True))
        command = batch()
        await service.store(command)
        row = db.outbox.rows['index:' + command['batch_id']]
        assert row['queue'] == SEARCH_INDEX_QUEUE and row['sent'] is False
        assert row['payload']['documents'][0]['document_id'] == command['documents'][0]['id']
        # Redelivery of the same batch is answered from the receipt: no second index event.
        await service.store(command)
        assert len(db.outbox.rows) == 2
        # Without the flag (main stack) nothing changes: one completion row per batch only.
        plain = Database()
        await CorpusCommandService(MongoCorpusRepository(plain)).store(batch())
        assert all('queue' not in r for r in plain.outbox.rows.values())
    asyncio.run(scenario())


def test_index_event_rolls_back_with_the_batch():
    async def scenario():
        db = Database()
        db.outbox.fail = True
        with pytest.raises(RuntimeError):
            await CorpusCommandService(MongoCorpusRepository(db, index_events=True)).store(batch())
        assert db.source_documents.rows == {} and db.outbox.rows == {}
    asyncio.run(scenario())


def test_backfill_streams_corpus_in_bounded_events():
    class Cursor:
        def __init__(self, rows): self.rows = rows
        def sort(self, *args): return self
        def batch_size(self, *args): return self
        def __aiter__(self):
            async def generate():
                for row in self.rows:
                    yield row
            return generate()

    class Collection:
        def __init__(self, rows): self.rows, self.where = rows, None
        def find(self, where, projection): self.where = where; return Cursor(self.rows)

    rows = [{**source_document(corpus_scope=scope, is_synthetic=scope == 'synthetic-cs'), '_id': str(uuid4()),
             'publication_status': 'published'} for scope in ['kaggle-cs'] * 120 + ['synthetic-cs'] * 130]
    published = []

    async def publish(payload):
        published.append(payload)

    summary = asyncio.run(backfill(Collection(rows), publish, batch_size=100, run_id='run'))
    assert summary['events'] == 3 and summary['documents'] == 250
    assert summary['documents_by_scope'] == {'kaggle-cs': 120, 'synthetic-cs': 130}
    assert [len(p['documents']) for p in published] == [100, 100, 50]
    assert {p['origin'] for p in published} == {'backfill'} and len({p['event_id'] for p in published}) == 3
    assert backfill_filter('all')['corpus_scope'] == {'$in': ['kaggle-cs', 'synthetic-cs']}
    with pytest.raises(ValueError):
        backfill_filter('other')


# ---------------------------------------------------------------- Search: projection and indexing
def test_projection_lifts_searchable_metadata_and_keeps_full_metadata():
    source = project(source_document())
    assert source['map_name'] == 'Mirage' and source['team1'] == 'Natus Vincere' and source['document_type'] == 'map'
    assert source['player_names'] == ['s1mple (Oleksandr Kostyliev), UA', 'ZywOo (Mathieu Herbaut), FR']
    assert source['metadata']['players'][0]['kills'] == 20 and source['is_synthetic'] is False
    assert set(source) <= set(INDEX_DEFINITION['mappings']['properties'])  # dynamic: strict must accept it


@pytest.mark.parametrize('changes', [
    {'document_id': 'nope'}, {'version': 0}, {'version': True}, {'corpus_scope': 'news'},
    {'is_synthetic': True},  # kaggle-cs must not be synthetic
    {'title': ' '}, {'metadata': {'document_type': 'article'}}])
def test_projection_rejects_invalid_documents(changes):
    with pytest.raises(DomainError):
        project(source_document(**changes))


def test_indexing_is_idempotent_by_document_id_and_version():
    async def scenario():
        index = MemoryIndex()
        service = DocumentIndexingService(index=index)
        document = source_document()
        first = await service.handle(event(document))
        again = await service.handle(event(document))  # redelivery / replay / backfill
        assert first['indexed'] == again['indexed'] == 1 and len(index.documents) == 1
        newer = {**document, 'version': 2, 'title': 'Renamed'}
        await service.handle(event(newer))
        stale = await service.handle(event(document))
        assert stale['stale'] == 1 and index.documents[document['document_id']]['title'] == 'Renamed'
        both = await service.handle(event(document, newer))  # duplicate id in one event: newest wins
        assert both['received'] == 2 and both['indexed'] == 1
    asyncio.run(scenario())


def test_invalid_event_is_rejected_before_any_write():
    async def scenario():
        index = MemoryIndex()
        service = DocumentIndexingService(index=index)
        with pytest.raises(DomainError):
            await service.handle(event(source_document(), source_document(corpus_scope='other')))
        with pytest.raises(DomainError):
            await service.handle(event(source_document(), event_type='other'))
        assert index.calls == 0
    asyncio.run(scenario())


def test_bulk_uses_external_version_and_classifies_failures():
    lines = bulk_payload([project(source_document())]).splitlines()
    action = json.loads(lines[0])['index']
    assert action['_index'] == ALIAS and action['version_type'] == 'external_gte' and action['version'] == 1
    ok = {'items': [{'index': {'status': 201}}, {'index': {'status': 200}}, {'index': {'status': 409}}]}
    assert summarize_bulk(ok) == {'indexed': 2, 'stale': 1}
    with pytest.raises(ValueError):
        summarize_bulk({'items': [{'index': {'status': 400, 'error': {'type': 'mapper_parsing_exception'}}}]})
    with pytest.raises(SearchBackendUnavailable):
        summarize_bulk({'items': [{'index': {'status': 429, 'error': {'type': 'es_rejected_execution_exception'}}}]})


# ---------------------------------------------------------------- Search: query DSL
@pytest.mark.parametrize('arguments', [
    {'mode': 'regex'}, {'corpus_scope': 'news'}, {'document_type': 'article'}, {'q': 'x' * 201},
    {'page_size': 51}, {'page': 0}, {'page': 501, 'page_size': 20}, {'map_name': 'm' * 65}])
def test_query_validation(arguments):
    with pytest.raises(ValueError):
        FullTextQuery(**arguments)


def test_search_body_modes():
    must = lambda **kw: build_search_body(FullTextQuery(**kw))['query']['bool']['must'][0]
    assert must(q='') == {'match_all': {}}
    all_words = must(q='  Vitality   Mirage ')['multi_match']
    assert all_words['type'] == 'cross_fields' and all_words['operator'] == 'and' and all_words['query'] == 'Vitality Mirage'
    assert {'team1^4', 'map_name.text^3', 'player_names^2', 'text'} <= set(all_words['fields'])
    assert must(q='a b', mode='phrase')['multi_match']['type'] == 'phrase'
    assert must(q='a b', mode='any')['multi_match']['operator'] == 'or'
    fuzzy = must(q='mirrage', mode='fuzzy')['multi_match']
    assert fuzzy['fuzziness'] == 'AUTO:5,9' and 'text' not in fuzzy['fields'] and 'player_names^2' in fuzzy['fields']


def test_search_body_filters_highlight_and_facets():
    body = build_search_body(FullTextQuery(q='s1mple', corpus_scope='kaggle-cs', include_synthetic=False,
                                           document_type='map', map_name='Mirage', page=3, page_size=10))
    assert body['query']['bool']['filter'] == [{'term': {'corpus_scope': 'kaggle-cs'}}, {'term': {'is_synthetic': False}},
                                               {'term': {'document_type': 'map'}}]
    assert body['post_filter'] == {'term': {'map_name': 'Mirage'}}  # map facet still lists every map
    assert body['aggs']['document_type']['filter'] == {'term': {'map_name': 'Mirage'}}
    assert body['from'] == 20 and body['size'] == 10 and body['track_total_hits'] is True
    assert body['sort'][0] == {'_score': 'desc'} and body['highlight']['pre_tags'] == ['\ue000']
    assert {'title', 'text', 'player_names', 'tournament'} <= set(body['highlight']['fields'])
    assert 'post_filter' not in build_search_body(FullTextQuery(q='x'))
    assert build_search_body(FullTextQuery(q='x'))['query']['bool']['filter'] == []


def test_parse_search_response():
    response = {'took': 7, 'timed_out': False, '_shards': {'failed': 0},
                'hits': {'total': {'value': 2, 'relation': 'eq'}, 'max_score': 9.5, 'hits': [
                    {'_id': 'a', '_score': 9.5, '_source': {**project(source_document()), 'text': 'x' * 300},
                     'highlight': {'map_name.text': ['\ue000Mirage\ue001'], 'text': ['… \ue000Mirage\ue001 …']}}]},
                'aggregations': {'map_name': {'buckets': [{'key': 'Mirage', 'doc_count': 2}]},
                                 'is_synthetic': {'doc_count': 2, 'values': {'buckets': [{'key': 0, 'key_as_string': 'false', 'doc_count': 2}]}},
                                 'corpus_scope': {'values': {'buckets': []}}, 'document_type': {'values': {'buckets': []}}}}
    parsed = parse_search_response(response)
    hit = parsed['hits'][0]
    assert parsed['total'] == 2 and parsed['took_ms'] == 7 and parsed['max_score'] == 9.5
    assert hit['score'] == 9.5 and set(hit['highlights']) == {'map_name', 'text'} and hit['snippet'].endswith('…')
    assert parsed['facets']['map_name'] == [{'value': 'Mirage', 'count': 2}]
    assert parsed['facets']['is_synthetic'] == [{'value': 'false', 'count': 2}]


def test_adapter_maps_transport_failures_to_unavailable():
    async def scenario():
        def refuse(request):
            raise httpx.ConnectError('refused', request=request)
        down = ElasticsearchDocumentIndex(url='http://es', client=httpx.AsyncClient(
            base_url='http://es', transport=httpx.MockTransport(refuse)))
        with pytest.raises(SearchBackendUnavailable):
            await down.search(FullTextQuery(q='x'))
        missing = ElasticsearchDocumentIndex(url='http://es', client=httpx.AsyncClient(
            base_url='http://es', transport=httpx.MockTransport(lambda r: httpx.Response(
                404, json={'error': {'type': 'index_not_found_exception'}}))))
        with pytest.raises(SearchBackendUnavailable):
            await missing.search(FullTextQuery(q='x'))
        seen = []
        def created(request):
            seen.append((request.method, request.url.path))
            return httpx.Response(404) if request.method == 'HEAD' else httpx.Response(200, json={'acknowledged': True})
        fresh = ElasticsearchDocumentIndex(url='http://es', client=httpx.AsyncClient(
            base_url='http://es', transport=httpx.MockTransport(created)))
        assert (await fresh.ensure_index())['created'] is True
        assert seen == [('HEAD', '/_alias/cs-documents'), ('PUT', '/cs-documents-v1')]
    asyncio.run(scenario())


# ---------------------------------------------------------------- Search: service and HTTP states
class FakeIndex:
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    async def search(self, query):
        if self.error:
            raise self.error
        return self.result

    async def status(self):
        if self.error:
            raise self.error
        return {'status': 'ok', 'documents': 100000}


FOUND = {'hits': [{'id': 'a', 'score': 3.2}], 'total': 1, 'timed_out': False, 'failed_shards': 0, 'took_ms': 4}
EMPTY = {'hits': [], 'total': 0, 'timed_out': False, 'failed_shards': 0, 'took_ms': 1}


def test_service_states():
    run = lambda result: asyncio.run(FullTextSearchService(index=FakeIndex(result)).search(FullTextQuery(q='x')))
    assert run(FOUND)['status'] == 'found' and run(FOUND)['degraded'] is False
    assert run(EMPTY)['status'] == 'empty'
    assert run({**FOUND, 'timed_out': True})['degraded'] is True


@pytest.mark.parametrize('index, url, status, state', [
    (FakeIndex(FOUND), '/api/v1/search?q=Mirage&mode=fuzzy&include_synthetic=false', 200, 'found'),
    (FakeIndex(EMPTY), '/api/v1/search?q=zzzz', 200, 'empty'),
    (FakeIndex(error=SearchBackendUnavailable('Elasticsearch unreachable: ConnectError')), '/api/v1/search?q=x', 503, 'degraded'),
    (FakeIndex(error=SearchBackendUnavailable('down')), '/api/v1/search/status', 503, 'degraded'),
    (FakeIndex(FOUND), '/api/v1/search?mode=regex', 422, None),
    (FakeIndex(FOUND), '/api/v1/search?page=501', 422, None)])
def test_http_states(index, url, status, state):
    with TestClient(search_app) as client:
        search_app.state.controller = FullTextSearchController(service=FullTextSearchService(index=index))
        response = client.get(url)
    assert response.status_code == status
    if state:
        assert response.json()['status'] == state


def test_http_unexpected_error_is_reported_as_error_state():
    with TestClient(search_app, raise_server_exceptions=False) as client:
        search_app.state.controller = FullTextSearchController(service=FullTextSearchService(index=FakeIndex(error=RuntimeError('bug'))))
        response = client.get('/api/v1/search?q=x')
    assert response.status_code == 500 and response.json()['status'] == 'error'


# ---------------------------------------------------------------- opt-in: running cs-sharded stand
STAND = os.environ.get('SEARCH_STAND_URL', 'http://127.0.0.1:8082')
stand = pytest.mark.skipif(os.environ.get('RUN_SEARCH_STACK_TESTS') != '1', reason='set RUN_SEARCH_STACK_TESTS=1')


def get(path, **params):
    url = STAND + path + ('?' + urllib.parse.urlencode(params) if params else '')
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.loads(response.read())


@pytest.mark.integration
@stand
def test_stand_index_holds_the_whole_corpus():
    status = get('/api/v1/search/status')
    assert status['documents'] == 100_000
    assert status['by_corpus_scope'] == {'kaggle-cs': 20_675, 'synthetic-cs': 79_325}


@pytest.mark.integration
@stand
def test_stand_search_found_filtered_and_empty():
    found = get('/api/v1/search', q='Mirage', document_type='map', include_synthetic='false')
    assert found['status'] == 'found' and found['total'] > 0
    assert all(h['is_synthetic'] is False and h['map_name'] == 'Mirage' for h in found['hits'])
    assert found['hits'][0]['score'] >= found['hits'][-1]['score'] and found['hits'][0]['highlights']
    synthetic = get('/api/v1/search', q='Synthetic Team', corpus_scope='synthetic-cs')
    assert synthetic['total'] > 0 and all(h['is_synthetic'] for h in synthetic['hits'])
    assert get('/api/v1/search', q='qwxzvj nonexistent', mode='all')['status'] == 'empty'


def test_highlight_markers_survive_lucene_fragment_trim():
    # Lucene trims fragments with String.trim() (every char <= U+0020): a control-char marker at the
    # start of a fragment was silently dropped on the stand, leaving an unopened highlight.
    from search_service.infrastructure.search.elasticsearch_documents import HIGHLIGHT_POST, HIGHLIGHT_PRE
    assert (HIGHLIGHT_PRE + 's1mple' + HIGHLIGHT_POST).strip() == HIGHLIGHT_PRE + 's1mple' + HIGHLIGHT_POST
    assert min(ord(HIGHLIGHT_PRE), ord(HIGHLIGHT_POST)) > 0x20
