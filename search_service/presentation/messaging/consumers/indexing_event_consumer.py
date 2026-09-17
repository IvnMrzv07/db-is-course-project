from __future__ import annotations

from dataclasses import dataclass
from contracts.messages import ChangeNotification
from search_service.application.services.commands.indexing_service import IndexingService


@dataclass(kw_only=True)
class IndexingEventConsumer:
    """Validate message before invocation; broker ack occurs only after durable success."""

    service: IndexingService

    async def handle(self, message: ChangeNotification) -> None:
        await self.service.handle(message)
