from __future__ import annotations

from typing import Protocol

from search_service.application.dtos.full_text_query import FullTextQuery


class SearchBackendUnavailable(Exception):
    """Transient search-engine failure (unreachable, timed out, red cluster, missing index).

    Queries map it to the degraded state (HTTP 503); the indexer requeues the event instead of
    quarantining it, so an Elasticsearch outage delays indexing but never loses events.
    """


class DocumentIndex(Protocol):
    """Outbound port for the full-text index of Content documents."""

    async def ensure_index(self) -> dict:
        """Create the versioned index and its alias if they do not exist."""
        ...

    async def upsert(self, documents: list[dict]) -> dict:
        """Idempotent bulk upsert by id with external version; returns {indexed, stale}."""
        ...

    async def search(self, query: FullTextQuery) -> dict:
        """Ranked, highlighted, filtered page of hits with facets and engine timing."""
        ...

    async def status(self) -> dict:
        """Cluster health, alias target and document counts by corpus scope."""
        ...
