from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from search_service.application.dtos.search_history_dto import SearchHistoryDTO
from search_service.application.ports.search_history import SearchHistory


@dataclass(kw_only=True)
class SearchStatisticsQueryService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    history: SearchHistory

    async def recent(self, actor_id: UUID, limit: int = 20) -> tuple[SearchHistoryDTO, ...]:
        """Authorize dashboard access and return bounded history"""
        raise NotImplementedError("Authorize dashboard access and return bounded history")
