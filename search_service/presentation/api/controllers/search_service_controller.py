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
from search_service.application.services.queries.search_service import SearchService


@dataclass(kw_only=True)
class SearchServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: SearchService

    async def search(self, query: SearchQueryDTO) -> SearchResultDTO:
        """Normalize semantic query, check cache, search and record outcome"""
        raise NotImplementedError("Normalize semantic query, check cache, search and record outcome")
