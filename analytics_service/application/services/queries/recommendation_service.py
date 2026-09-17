from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from analytics_service.application.dtos.comparison_query import ComparisonQuery
from analytics_service.application.dtos.team_comparison_dto import TeamComparisonDTO
from analytics_service.application.dtos.recommendation_dto import RecommendationDTO
from analytics_service.application.ports.statistics_reader import StatisticsReader


@dataclass(kw_only=True)
class RecommendationService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    reader: StatisticsReader

    async def recommend_matches(self, team_id: UUID, limit: int = 10) -> tuple[RecommendationDTO, ...]:
        """Recommend available recorded matches with explicit ranking reasons"""
        raise NotImplementedError("Recommend available recorded matches with explicit ranking reasons")
