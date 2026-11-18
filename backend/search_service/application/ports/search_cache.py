from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from search_service.application.dtos.search_query_dto import SearchQueryDTO
from search_service.application.dtos.search_result_dto import SearchResultDTO


class SearchCache(Protocol):
    """Outbound port owned by this application."""

    async def get(self, key: str) -> SearchResultDTO | None:
        """Read normalized result cache"""
        ...

    async def put(self, key: str, result: SearchResultDTO, ttl_seconds: int) -> None:
        """Cache results including empty hits"""
        ...

    async def invalidate(self, corpus_scope: str) -> None:
        """Advance cache generation"""
        ...
