from __future__ import annotations

from dataclasses import dataclass
from contracts.messages import BatchCompleted
from ingestion_service.application.services.commands.batch_completion_service import BatchCompletionService


@dataclass(kw_only=True)
class BatchCompletedConsumer:
    """Validate message before invocation; broker ack occurs only after durable success."""

    service: BatchCompletionService

    async def handle(self, message: BatchCompleted) -> None:
        await self.service.handle(message)
