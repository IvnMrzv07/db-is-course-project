from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from analytics_service.application.dtos.comparison_query import ComparisonQuery
from analytics_service.application.dtos.team_comparison_dto import TeamComparisonDTO
from analytics_service.application.dtos.recommendation_dto import RecommendationDTO


@dataclass(kw_only=True)
class PostgresStatisticsReader:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def compare(self, query: ComparisonQuery) -> TeamComparisonDTO:
        """Read local analytical tables"""
        raise NotImplementedError("Read local analytical tables")

    async def recommend_matches(self, team_id: UUID, limit: int) -> tuple[RecommendationDTO, ...]:
        """Return explainable recorded-game recommendations"""
        raise NotImplementedError("Return explainable recorded-game recommendations")
