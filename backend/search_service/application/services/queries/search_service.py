from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from search_service.application.dtos.search_query_dto import SearchQueryDTO
from search_service.application.dtos.search_result_dto import SearchResultDTO
from search_service.application.dtos.search_history_dto import SearchHistoryDTO
from search_service.application.ports.search_reader import SearchReader
from search_service.application.ports.search_cache import SearchCache
from search_service.application.ports.search_history import SearchHistory


@dataclass(kw_only=True)
class SearchService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    reader: SearchReader
    cache: SearchCache
    history: SearchHistory

    async def search(self, query: SearchQueryDTO) -> SearchResultDTO:
        """Normalize semantic query, check cache, search and record outcome"""
        raise NotImplementedError("Normalize semantic query, check cache, search and record outcome")
