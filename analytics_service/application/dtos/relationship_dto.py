from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class RelationshipDTO:
    """Typed application boundary data."""

    player_ids: tuple[UUID, ...]
    team_ids: tuple[UUID, ...]
    evidence_match_ids: tuple[UUID, ...]
    relationship_kind: str
    observed_from: datetime | None
    observed_until: datetime | None
