from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from search_service.application.dtos.search_history_dto import SearchHistoryDTO


class SearchHistory(Protocol):
    """Outbound port owned by this application."""

    async def record(self, entry: SearchHistoryDTO) -> None:
        """Store bounded query outcome telemetry, including cache hits"""
        ...

    async def recent(self, limit: int) -> tuple[SearchHistoryDTO, ...]:
        """Read recent history for authorized monitoring"""
        ...
