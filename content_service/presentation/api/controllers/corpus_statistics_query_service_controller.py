from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from content_service.application.dtos.corpus_statistics_dto import CorpusStatisticsDTO
from content_service.application.ports.corpus_statistics import CorpusStatisticsReader
from content_service.application.services.queries.corpus_statistics_query_service import CorpusStatisticsQueryService


@dataclass(kw_only=True)
class CorpusStatisticsQueryServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: CorpusStatisticsQueryService

    async def get(self, corpus_scope: str, *, actor_id: UUID) -> CorpusStatisticsDTO:
        """Authorize monitoring and return persisted count sample"""
        raise NotImplementedError("Authorize monitoring and return persisted count sample")
