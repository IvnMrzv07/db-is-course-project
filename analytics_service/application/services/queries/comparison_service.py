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


@dataclass(kw_only=True)
class ComparisonService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    reader: StatisticsReader
    cache: ComparisonCache

    async def compare(self, query: ComparisonQuery) -> TeamComparisonDTO:
        """Validate period, cache lookup, local read and result timestamp"""
        raise NotImplementedError("Validate period, cache lookup, local read and result timestamp")
