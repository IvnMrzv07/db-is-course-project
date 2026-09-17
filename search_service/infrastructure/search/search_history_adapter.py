from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from search_service.application.dtos.search_history_dto import SearchHistoryDTO


@dataclass(kw_only=True)
class ElasticsearchHistory:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def record(self, entry: SearchHistoryDTO) -> None:
        """Store bounded query outcome telemetry, including cache hits"""
        raise NotImplementedError("Store bounded query outcome telemetry, including cache hits")

    async def recent(self, limit: int) -> tuple[SearchHistoryDTO, ...]:
        """Read recent history for authorized monitoring"""
        raise NotImplementedError("Read recent history for authorized monitoring")
