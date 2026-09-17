from __future__ import annotations

from dataclasses import dataclass
from contracts.messages import ImportMatchBatch
from competition_service.application.services.commands.import_match_service import ImportMatchService


@dataclass(kw_only=True)
class ImportMatchConsumer:
    """Validate message before invocation; broker ack occurs only after durable success."""

    service: ImportMatchService

    async def handle(self, message: ImportMatchBatch) -> None:
        await self.service.import_batch(message)
