from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class PlayerConnection:
    """Graph evidence, not an inferred permanent contract or exact transfer date."""

    player1_id: UUID
    player2_id: UUID
    team_id: UUID
    evidence_match_ids: tuple[UUID, ...]
    first_observed_at: datetime
    last_observed_at: datetime
