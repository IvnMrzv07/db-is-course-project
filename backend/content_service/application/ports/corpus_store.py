from typing import Protocol
from uuid import UUID
from content_service.application.dtos.document_query import DocumentQuery


class StoreUnavailable(Exception):
    """The document database cannot commit now (shard or primary absent, timeout).

    The batch itself is valid: consumers requeue it without spending a processing attempt, so an outage of any
    length delays writes but never quarantines data or fails a job.
    """


class CorpusStore(Protocol):
    async def browse(self, query: DocumentQuery) -> dict: ...
    async def read(self, document_id: UUID) -> dict | None: ...
    async def statistics(self) -> dict: ...
    async def persist_batch(self, batch: dict) -> dict: ...
