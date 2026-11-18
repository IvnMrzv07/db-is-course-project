from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from analytics_service.application.dtos.comparison_query import ComparisonQuery
from analytics_service.application.dtos.team_comparison_dto import TeamComparisonDTO
from analytics_service.application.dtos.recommendation_dto import RecommendationDTO


class ComparisonCache(Protocol):
    """Outbound port owned by this application."""

    async def get(self, key: str) -> TeamComparisonDTO | None:
        """Read cached comparison"""
        ...

    async def put(self, key: str, value: TeamComparisonDTO, ttl_seconds: int) -> None:
        """Cache with bounded lifetime"""
        ...

    async def invalidate(self, team_id: UUID) -> None:
        """Invalidate affected comparison generation"""
        ...
