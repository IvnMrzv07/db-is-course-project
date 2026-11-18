from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import ChangeNotification
from analytics_service.application.ports.statistics_projection import StatisticsProjection


@dataclass(kw_only=True)
class StatisticsProjectionService:
    """Independent projection command handler; never spans graph and SQL transactions."""

    projection: StatisticsProjection

    async def handle(self, event: ChangeNotification) -> None:
        """Validate source version and apply projection"""
        raise NotImplementedError("Validate source version and apply projection")

    async def rebuild(self) -> None:
        """Rebuild without losing concurrent updates"""
        raise NotImplementedError("Rebuild without losing concurrent updates")
