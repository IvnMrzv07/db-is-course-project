from __future__ import annotations

from dataclasses import dataclass
from contracts.messages import ChangeNotification
from analytics_service.application.services.commands.graph_projection_service import GraphProjectionService


@dataclass(kw_only=True)
class GraphEventConsumer:
    """Validate message before invocation; broker ack occurs only after durable success."""

    service: GraphProjectionService

    async def handle(self, message: ChangeNotification) -> None:
        await self.service.handle(message)
