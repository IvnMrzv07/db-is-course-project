from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import ChangeNotification
from analytics_service.application.ports.graph_projection import GraphProjection


@dataclass(kw_only=True)
class GraphProjectionService:
    """Independent projection command handler; never spans graph and SQL transactions."""

    projection: GraphProjection

    async def handle(self, event: ChangeNotification) -> None:
        """Validate source version and apply projection"""
        raise NotImplementedError("Validate source version and apply projection")

    async def rebuild(self) -> None:
        """Rebuild without losing concurrent updates"""
        raise NotImplementedError("Rebuild without losing concurrent updates")
