from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from search_service.application.dtos.search_history_dto import SearchHistoryDTO
from search_service.application.ports.search_history import SearchHistory
from search_service.application.services.queries.search_statistics_query_service import SearchStatisticsQueryService


@dataclass(kw_only=True)
class SearchStatisticsQueryServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: SearchStatisticsQueryService

    async def recent(self, actor_id: UUID, limit: int = 20) -> tuple[SearchHistoryDTO, ...]:
        """Authorize dashboard access and return bounded history"""
        raise NotImplementedError("Authorize dashboard access and return bounded history")
