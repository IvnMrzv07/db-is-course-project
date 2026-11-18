from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from analytics_service.application.dtos.comparison_query import ComparisonQuery
from analytics_service.application.dtos.team_comparison_dto import TeamComparisonDTO
from analytics_service.application.dtos.recommendation_dto import RecommendationDTO
from analytics_service.application.ports.statistics_reader import StatisticsReader
from analytics_service.application.ports.comparison_cache import ComparisonCache
from analytics_service.application.services.queries.comparison_service import ComparisonService


@dataclass(kw_only=True)
class ComparisonServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: ComparisonService

    async def compare(self, query: ComparisonQuery) -> TeamComparisonDTO:
        """Validate period, cache lookup, local read and result timestamp"""
        raise NotImplementedError("Validate period, cache lookup, local read and result timestamp")
