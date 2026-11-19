from __future__ import annotations

from dataclasses import dataclass

from search_service.application.services.commands.document_indexing_service import DocumentIndexingService


@dataclass(kw_only=True)
class DocumentIndexConsumer:
    """`search.index` handler; the broker acks only after this returns (durable bulk upsert)."""

    service: DocumentIndexingService

    async def handle(self, payload: dict) -> dict:
        return await self.service.handle(payload)
