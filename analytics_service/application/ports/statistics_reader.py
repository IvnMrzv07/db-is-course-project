from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from analytics_service.application.dtos.comparison_query import ComparisonQuery
from analytics_service.application.dtos.team_comparison_dto import TeamComparisonDTO
from analytics_service.application.dtos.recommendation_dto import RecommendationDTO


class StatisticsReader(Protocol):
    """Outbound port owned by this application."""

    async def compare(self, query: ComparisonQuery) -> TeamComparisonDTO:
        """Read local analytical tables"""
        ...

    async def recommend_matches(self, team_id: UUID, limit: int) -> tuple[RecommendationDTO, ...]:
        """Return explainable recorded-game recommendations"""
        ...
