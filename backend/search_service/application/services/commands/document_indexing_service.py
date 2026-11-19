from __future__ import annotations

import logging
from dataclasses import dataclass

from contracts.messages import SEARCH_INDEX_EVENT_TYPE, SEARCH_INDEX_SCHEMA_VERSION
from search_service.application.ports.document_index import DocumentIndex
from search_service.domain.exceptions import DomainError
from search_service.domain.services.index_projection import project

log = logging.getLogger(__name__)
MAX_DOCUMENTS_PER_EVENT = 500


@dataclass(kw_only=True)
class DocumentIndexingService:
    """Handles `search.index` events: validate the whole event, then one idempotent bulk upsert.

    Idempotency is per document id: the index stores the owner's version as external version
    (`external_gte`), so redelivered, replayed and backfill events overwrite with identical data and
    an older version can never replace a newer one (reported as `stale`, not as an error).
    """

    index: DocumentIndex

    async def handle(self, event: dict) -> dict:
        if event.get('event_type') != SEARCH_INDEX_EVENT_TYPE:
            raise DomainError('Unsupported event type')
        if event.get('schema_version') != SEARCH_INDEX_SCHEMA_VERSION:
            raise DomainError('Unsupported event schema version')
        documents = event.get('documents')
        if not isinstance(documents, list) or len(documents) > MAX_DOCUMENTS_PER_EVENT:
            raise DomainError('Event must carry a bounded list of documents')
        projected: dict[str, dict] = {}
        for document in documents:
            source = project(document)
            previous = projected.get(source['id'])
            if previous is None or previous['version'] <= source['version']:
                projected[source['id']] = source  # duplicate ids inside one event: keep the newest
        result = await self.index.upsert(list(projected.values())) if projected else {'indexed': 0, 'stale': 0}
        result = {'event_id': event.get('event_id'), 'origin': event.get('origin'), 'received': len(documents), **result}
        log.info('Indexed event=%s origin=%s received=%s indexed=%s stale=%s', result['event_id'],
                 result['origin'], result['received'], result['indexed'], result['stale'])
        return result
