from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .player_map_stats import PlayerMapStats

@dataclass(frozen=True, kw_only=True)
class MapResult:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    match_id: UUID
    map_name: str
    map_number: int
    team1_rounds: int | None
    team2_rounds: int | None
    player_stats: tuple[PlayerMapStats, ...]
