from __future__ import annotations

from dataclasses import dataclass
from contracts.messages import ChangeNotification
from analytics_service.application.services.commands.statistics_projection_service import StatisticsProjectionService


@dataclass(kw_only=True)
class StatisticsEventConsumer:
    """Validate message before invocation; broker ack occurs only after durable success."""

    service: StatisticsProjectionService

    async def handle(self, message: ChangeNotification) -> None:
        await self.service.handle(message)
