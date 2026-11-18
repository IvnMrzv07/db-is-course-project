from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class TeamMembership:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    player_id: UUID
    team_id: UUID
    valid_from: datetime | None
    valid_until: datetime | None
    source_url: str
    evidence_kind: str
