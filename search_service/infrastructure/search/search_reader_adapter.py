from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from search_service.application.dtos.search_query_dto import SearchQueryDTO
from search_service.application.dtos.search_result_dto import SearchResultDTO


@dataclass(kw_only=True)
class ElasticsearchReader:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def search(self, query: SearchQueryDTO) -> SearchResultDTO:
        """Execute bounded full-text query with snippets and highlights"""
        raise NotImplementedError("Execute bounded full-text query with snippets and highlights")
