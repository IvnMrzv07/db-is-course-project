from __future__ import annotations

import time
from dataclasses import dataclass

from search_service.application.dtos.full_text_query import FullTextQuery
from search_service.application.ports.document_index import DocumentIndex


@dataclass(kw_only=True)
class FullTextSearchService:
    """Full-text query use case: Found / Empty states, timings; backend failures propagate as
    SearchBackendUnavailable for the degraded state."""

    index: DocumentIndex

    async def search(self, query: FullTextQuery) -> dict:
        started = time.perf_counter()
        result = await self.index.search(query)
        hits = result.get('hits', [])
        return {
            **result,
            'status': 'found' if hits else 'empty',
            # A partial answer (engine timeout or failed index shards) is shown, but flagged.
            'degraded': bool(result.get('timed_out') or result.get('failed_shards')),
            'query': {'q': query.text, 'mode': query.mode, 'corpus_scope': query.corpus_scope,
                      'document_type': query.document_type, 'map_name': query.map_name,
                      'include_synthetic': query.include_synthetic},
            'page': query.page, 'page_size': query.page_size,
            'elapsed_ms': round((time.perf_counter() - started) * 1000, 1),
        }

    async def status(self) -> dict:
        return await self.index.status()
