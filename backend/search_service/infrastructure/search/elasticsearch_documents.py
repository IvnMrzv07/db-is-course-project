"""Elasticsearch adapter for the document index (REST over httpx; no security on the local stand).

Index `cs-documents-v1` behind alias `cs-documents`: a future mapping change creates v2 and moves
the alias after a backfill, without a search outage.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import httpx

from search_service.application.dtos.full_text_query import FullTextQuery
from search_service.application.ports.document_index import SearchBackendUnavailable

ALIAS = 'cs-documents'
INDEX = 'cs-documents-v1'
# Private Use Area markers: the UI splits on them, no HTML is trusted. Not control chars: Lucene trims
# fragments with String.trim(), which strips every char <= U+0020 (a leading match lost its marker).
HIGHLIGHT_PRE, HIGHLIGHT_POST = '\ue000', '\ue001'
SEARCH_FIELDS = ('title^3', 'team1^4', 'team2^4', 'tournament^2', 'map_name.text^3', 'player_names^2', 'text')
# Typo tolerance only on short name fields, max 1 edit below 9 characters: with AUTO (2 edits from 6 chars)
# highlighting the expanded terms took ~1 s on 100k docs, AUTO:5,9 keeps the same hits at ~0.2 s.
FUZZY_FIELDS = tuple(f for f in SEARCH_FIELDS if not f.startswith('text'))
SNIPPET_CHARACTERS = 240

_TEXT_WITH_KEYWORD = {'type': 'text', 'analyzer': 'cs_text',
                      'fields': {'keyword': {'type': 'keyword', 'ignore_above': 256}}}
INDEX_DEFINITION = {
    'settings': {
        'number_of_shards': 1, 'number_of_replicas': 0, 'refresh_interval': '1s',
        'analysis': {'analyzer': {'cs_text': {'type': 'custom', 'tokenizer': 'standard',
                                              'filter': ['lowercase', 'asciifolding']}}},
    },
    'mappings': {
        'dynamic': 'strict',
        'properties': {
            'id': {'type': 'keyword'}, 'version': {'type': 'long'},
            'title': _TEXT_WITH_KEYWORD, 'text': {'type': 'text', 'analyzer': 'cs_text'},
            'language': {'type': 'keyword'}, 'corpus_scope': {'type': 'keyword'},
            'is_synthetic': {'type': 'boolean'}, 'source_id': {'type': 'keyword'},
            'document_type': {'type': 'keyword'},
            'map_name': {'type': 'keyword', 'fields': {'text': {'type': 'text', 'analyzer': 'cs_text'}}},
            'team1': _TEXT_WITH_KEYWORD, 'team2': _TEXT_WITH_KEYWORD, 'tournament': _TEXT_WITH_KEYWORD,
            'winner_team': _TEXT_WITH_KEYWORD, 'player_names': {'type': 'text', 'analyzer': 'cs_text'},
            'played_at': {'type': 'date', 'ignore_malformed': True}, 'best_of': {'type': 'integer'},
            'template_version': {'type': 'keyword'},
            # Kept verbatim in _source for display (players list included); not indexed -> no mapping explosion.
            'metadata': {'type': 'object', 'enabled': False},
        },
    },
}


def text_query(query: FullTextQuery) -> dict:
    text = query.text
    if not text:
        return {'match_all': {}}
    if query.mode == 'phrase':
        return {'multi_match': {'query': text, 'type': 'phrase', 'fields': list(SEARCH_FIELDS)}}
    if query.mode == 'any':
        return {'multi_match': {'query': text, 'type': 'best_fields', 'operator': 'or', 'fields': list(SEARCH_FIELDS)}}
    if query.mode == 'fuzzy':
        return {'multi_match': {'query': text, 'type': 'best_fields', 'operator': 'and', 'fuzziness': 'AUTO:5,9',
                                'prefix_length': 1, 'max_expansions': 20, 'fields': list(FUZZY_FIELDS)}}
    # all: every word must match, but words may come from different fields (team + map + player).
    return {'multi_match': {'query': text, 'type': 'cross_fields', 'operator': 'and', 'fields': list(SEARCH_FIELDS)}}


def scope_filters(query: FullTextQuery) -> list[dict]:
    filters = []
    if query.corpus_scope != 'all':
        filters.append({'term': {'corpus_scope': query.corpus_scope}})
    if not query.include_synthetic:
        filters.append({'term': {'is_synthetic': False}})
    if query.document_type:
        filters.append({'term': {'document_type': query.document_type}})
    return filters


def build_search_body(query: FullTextQuery) -> dict:
    """Query DSL: scoring query + non-scoring filters; the map filter is a post_filter so the map facet
    still lists every map for the current text query (other facets apply it explicitly)."""
    map_filter = {'term': {'map_name': query.map_name}} if query.map_name else None
    within_map = {'filter': map_filter or {'match_all': {}}}
    body = {
        'query': {'bool': {'must': [text_query(query)], 'filter': scope_filters(query)}},
        'from': query.offset, 'size': query.page_size, 'track_total_hits': True, 'timeout': '3s',
        'sort': [{'_score': 'desc'}, {'played_at': {'order': 'desc', 'missing': '_last'}}, {'id': 'asc'}],
        'track_scores': True,
        '_source': {'excludes': ['metadata.players']},
        'highlight': {
            'pre_tags': [HIGHLIGHT_PRE], 'post_tags': [HIGHLIGHT_POST], 'encoder': 'default',
            'fields': {'title': {'number_of_fragments': 0}, 'team1': {'number_of_fragments': 0},
                       'team2': {'number_of_fragments': 0}, 'tournament': {'number_of_fragments': 0},
                       'map_name.text': {'number_of_fragments': 0},
                       'player_names': {'number_of_fragments': 5, 'fragment_size': 80},
                       'text': {'number_of_fragments': 3, 'fragment_size': 160}},
        },
        'aggs': {
            'map_name': {'terms': {'field': 'map_name', 'size': 30}},
            'corpus_scope': {**within_map, 'aggs': {'values': {'terms': {'field': 'corpus_scope'}}}},
            'document_type': {**within_map, 'aggs': {'values': {'terms': {'field': 'document_type'}}}},
            'is_synthetic': {**within_map, 'aggs': {'values': {'terms': {'field': 'is_synthetic'}}}},
        },
    }
    if map_filter:
        body['post_filter'] = map_filter
    return body


def _buckets(aggregation: dict | None) -> list[dict]:
    if not aggregation:
        return []
    buckets = aggregation.get('values', aggregation).get('buckets', [])
    return [{'value': b.get('key_as_string', b['key']), 'count': b['doc_count']} for b in buckets]


def parse_search_response(response: dict) -> dict:
    hits = []
    for hit in response.get('hits', {}).get('hits', []):
        source = hit.get('_source', {})
        highlights = {name.removesuffix('.text'): fragments for name, fragments in (hit.get('highlight') or {}).items()}
        text = source.get('text') or ''
        hits.append({
            'id': hit['_id'], 'score': hit.get('_score'), 'title': source.get('title'),
            'snippet': text[:SNIPPET_CHARACTERS] + ('…' if len(text) > SNIPPET_CHARACTERS else ''),
            'highlights': highlights, 'corpus_scope': source.get('corpus_scope'),
            'is_synthetic': source.get('is_synthetic'), 'document_type': source.get('document_type'),
            'map_name': source.get('map_name'), 'team1': source.get('team1'), 'team2': source.get('team2'),
            'tournament': source.get('tournament'), 'played_at': source.get('played_at'),
            'source_id': source.get('source_id'), 'version': source.get('version'),
            'metadata': source.get('metadata') or {},
        })
    total = response.get('hits', {}).get('total', {'value': 0, 'relation': 'eq'})
    aggregations = response.get('aggregations', {})
    return {
        'total': total.get('value', 0), 'total_relation': total.get('relation', 'eq'),
        'max_score': response.get('hits', {}).get('max_score'), 'hits': hits,
        'took_ms': response.get('took'), 'timed_out': bool(response.get('timed_out')),
        'failed_shards': response.get('_shards', {}).get('failed', 0),
        'facets': {name: _buckets(aggregations.get(name)) for name in ('map_name', 'corpus_scope', 'document_type', 'is_synthetic')},
    }


def bulk_payload(documents: list[dict], index: str = ALIAS) -> str:
    lines = []
    for document in documents:
        lines.append(json.dumps({'index': {'_index': index, '_id': document['id'], 'version': document['version'],
                                           'version_type': 'external_gte'}}))
        lines.append(json.dumps(document, ensure_ascii=False))
    return '\n'.join(lines) + '\n'


def summarize_bulk(response: dict) -> dict:
    """409 version conflicts are stale events (a newer version is indexed): skipped, not failures."""
    indexed = stale = 0
    failures = []
    for item in response.get('items', []):
        result = item.get('index', {})
        status = result.get('status', 500)
        if status < 300:
            indexed += 1
        elif status == 409:
            stale += 1
        else:
            failures.append({'id': result.get('_id'), 'status': status, 'error': (result.get('error') or {}).get('type')})
    if failures:
        transient = any(f['status'] in (429, 503) or f['status'] >= 500 for f in failures)
        message = f'Bulk indexing failed for {len(failures)} documents: {failures[:3]}'
        raise SearchBackendUnavailable(message) if transient else ValueError(message)
    return {'indexed': indexed, 'stale': stale}


@dataclass(kw_only=True)
class ElasticsearchDocumentIndex:
    url: str
    timeout_seconds: float = 5.0
    client: httpx.AsyncClient | None = field(default=None, repr=False)

    def __post_init__(self):
        if self.client is None:
            self.client = httpx.AsyncClient(base_url=self.url.rstrip('/'), timeout=self.timeout_seconds)

    async def close(self) -> None:
        await self.client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = await self.client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:  # connect/read timeouts, refused connections, protocol errors
            raise SearchBackendUnavailable(f'Elasticsearch unreachable: {type(exc).__name__}') from exc
        if response.status_code in (429, 502, 503, 504) or response.status_code >= 500:
            raise SearchBackendUnavailable(f'Elasticsearch returned HTTP {response.status_code}')
        if response.status_code == 404 and 'index_not_found' in response.text:
            raise SearchBackendUnavailable('Search index does not exist yet; run the backfill')
        return response

    async def ensure_index(self) -> dict:
        exists = await self._request('HEAD', f'/_alias/{ALIAS}')
        if exists.status_code == 200:
            return {'created': False, 'alias': ALIAS}
        created = await self._request('PUT', f'/{INDEX}', json={**INDEX_DEFINITION, 'aliases': {ALIAS: {}}})
        if created.status_code >= 300 and 'resource_already_exists' not in created.text:
            raise RuntimeError(f'Cannot create index: {created.status_code} {created.text[:300]}')
        return {'created': created.status_code < 300, 'alias': ALIAS, 'index': INDEX}

    async def recreate_index(self) -> dict:
        await self._request('DELETE', f'/{INDEX}', params={'ignore_unavailable': 'true'})
        return await self.ensure_index()

    async def upsert(self, documents: list[dict]) -> dict:
        if not documents:
            return {'indexed': 0, 'stale': 0}
        response = await self._request('POST', '/_bulk', content=bulk_payload(documents).encode('utf-8'),
                                       headers={'Content-Type': 'application/x-ndjson'})
        if response.status_code >= 300:
            raise ValueError(f'Bulk request rejected: {response.status_code} {response.text[:300]}')
        return summarize_bulk(response.json())

    async def search(self, query: FullTextQuery) -> dict:
        response = await self._request('POST', f'/{ALIAS}/_search', json=build_search_body(query))
        if response.status_code >= 300:
            raise ValueError(f'Search request rejected: {response.status_code} {response.text[:300]}')
        return {**parse_search_response(response.json()), 'index': ALIAS}

    async def status(self) -> dict:
        health = (await self._request('GET', '/_cluster/health')).json()
        count = (await self._request('GET', f'/{ALIAS}/_count')).json()
        scopes = (await self._request('POST', f'/{ALIAS}/_search', json={
            'size': 0, 'track_total_hits': True,
            'aggs': {'corpus_scope': {'terms': {'field': 'corpus_scope'}},
                     'document_type': {'terms': {'field': 'document_type'}},
                     'is_synthetic': {'terms': {'field': 'is_synthetic'}}}})).json()
        aliases = (await self._request('GET', f'/_alias/{ALIAS}')).json()
        aggregations = scopes.get('aggregations', {})
        return {'status': 'ok' if health.get('status') in ('green', 'yellow') else 'degraded',
                'cluster': {'name': health.get('cluster_name'), 'health': health.get('status'),
                            'nodes': health.get('number_of_nodes')},
                'alias': ALIAS, 'indices': sorted(aliases), 'documents': count.get('count', 0),
                'by_corpus_scope': {b['value']: b['count'] for b in _buckets(aggregations.get('corpus_scope'))},
                'by_document_type': {b['value']: b['count'] for b in _buckets(aggregations.get('document_type'))},
                'by_is_synthetic': {str(b['value']): b['count'] for b in _buckets(aggregations.get('is_synthetic'))}}
