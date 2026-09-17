from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class PlayerMapStatsDTO:
    player_id: UUID
    team_id: UUID
    kills: int | None
    deaths: int | None
    assists: int | None
    adr: float | None
    kast: float | None


@dataclass(frozen=True, kw_only=True)
class MapResultDTO:
    id: UUID
    map_name: str
    map_number: int
    team1_rounds: int | None
    team2_rounds: int | None
    player_stats: tuple[PlayerMapStatsDTO, ...]


@dataclass(frozen=True, kw_only=True)
class MatchLineupDTO:
    team_id: UUID
    player_ids: tuple[UUID, ...]
