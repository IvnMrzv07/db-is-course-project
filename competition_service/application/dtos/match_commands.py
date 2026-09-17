from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .match_components_dto import MapResultDTO, MatchLineupDTO

@dataclass(frozen=True, kw_only=True)
class CreateMatch:
    """Creation input; authorization and idempotency must be checked by the command service."""

    tournament_id: UUID
    team1_id: UUID
    team2_id: UUID
    started_at: datetime
    best_of: int
    team1_series_score: int | None
    team2_series_score: int | None
    status: str
    map_results: tuple[MapResultDTO, ...]
    lineups: tuple[MatchLineupDTO, ...]
    actor_id: UUID
    idempotency_key: str


@dataclass(frozen=True, kw_only=True)
class UpdateMatch:
    """Full replacement; explicit null values clear nullable fields."""

    id: UUID
    expected_version: int
    tournament_id: UUID
    team1_id: UUID
    team2_id: UUID
    started_at: datetime
    best_of: int
    team1_series_score: int | None
    team2_series_score: int | None
    status: str
    map_results: tuple[MapResultDTO, ...]
    lineups: tuple[MatchLineupDTO, ...]
    actor_id: UUID
