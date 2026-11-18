from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .map_result import MapResult
from .match_lineup import MatchLineup

@dataclass(frozen=True, kw_only=True)
class Match:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    tournament_id: UUID
    team1_id: UUID
    team2_id: UUID
    started_at: datetime
    best_of: int
    team1_series_score: int | None
    team2_series_score: int | None
    status: str
    map_results: tuple[MapResult, ...]
    lineups: tuple[MatchLineup, ...]
