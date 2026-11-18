from __future__ import annotations

from dataclasses import dataclass
from contracts.messages import StoreSourceDocumentBatch
from content_service.application.services.commands.source_document_command_service import SourceDocumentCommandService


@dataclass(kw_only=True)
class SourceDocumentBatchConsumer:
    """Validate message before invocation; broker ack occurs only after durable success."""

    service: SourceDocumentCommandService

    async def handle(self, message: StoreSourceDocumentBatch) -> None:
        await self.service.store_batch(message)
