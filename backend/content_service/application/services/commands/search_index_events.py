"""Builds `search.index` events (contracts.IndexSourceDocuments, JSON form) from committed Content documents.

Pure functions: the repository calls them inside the batch transaction (outbox row) and the backfill
command calls them while streaming the collection. Search never reads Content's database.
"""
from datetime import datetime, timezone
from uuid import UUID
from contracts.messages import SEARCH_INDEX_EVENT_TYPE, SEARCH_INDEX_SCHEMA_VERSION

PRODUCER = 'content_service'
# Fields copied into the index projection; storage-only fields (stored_at, provider URLs...) stay in Content.
DOCUMENT_FIELDS = ('title', 'text', 'language', 'corpus_scope', 'is_synthetic', 'source_id', 'metadata')


def indexable_document(document: dict) -> dict | None:
    """Projection of one stored/ingested document; drafts and other statuses are never emitted."""
    if document.get('publication_status', 'published') != 'published':
        return None
    document_id = str(UUID(str(document.get('id', document.get('_id')))))
    projection = {'document_id': document_id, 'version': int(document.get('version', 1))}
    for field in DOCUMENT_FIELDS:
        projection[field] = document.get(field)
    projection['metadata'] = dict(projection['metadata'] or {})
    return projection


def index_event(batch_id: str, documents, *, origin: str = 'store', event_id: str | None = None,
                now: datetime | None = None) -> dict:
    if origin not in ('store', 'backfill'):
        raise ValueError('Unknown index event origin')
    projected = [p for p in (indexable_document(d) for d in documents) if p is not None]
    return {'event_id': event_id or f'index:{batch_id}', 'event_type': SEARCH_INDEX_EVENT_TYPE,
            'schema_version': SEARCH_INDEX_SCHEMA_VERSION, 'producer': PRODUCER,
            'occurred_at': (now or datetime.now(timezone.utc)).isoformat(), 'origin': origin,
            'batch_id': str(batch_id), 'documents': projected}
