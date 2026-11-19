from __future__ import annotations

from dataclasses import dataclass

from search_service.application.dtos.full_text_query import FullTextQuery
from search_service.application.services.queries.full_text_search_service import FullTextSearchService


@dataclass(kw_only=True)
class FullTextSearchController:
    """HTTP boundary for `/api/v1/search`; error translation happens in the FastAPI app."""

    service: FullTextSearchService

    async def search(self, query: FullTextQuery) -> dict:
        return await self.service.search(query)

    async def status(self) -> dict:
        return await self.service.status()
