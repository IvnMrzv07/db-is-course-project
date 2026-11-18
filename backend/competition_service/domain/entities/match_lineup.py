from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class MatchLineup:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    match_id: UUID
    team_id: UUID
    player_ids: tuple[UUID, ...]
