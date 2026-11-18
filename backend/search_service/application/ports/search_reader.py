from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from search_service.application.dtos.search_query_dto import SearchQueryDTO
from search_service.application.dtos.search_result_dto import SearchResultDTO


class SearchReader(Protocol):
    """Outbound port owned by this application."""

    async def search(self, query: SearchQueryDTO) -> SearchResultDTO:
        """Execute bounded full-text query with snippets and highlights"""
        ...
