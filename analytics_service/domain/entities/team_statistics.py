from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class TeamStatistics:
    """Derived statistics; formulas and missing-result policy must be defined before use."""

    team_id: UUID
    starts_at: datetime
    ends_at: datetime
    matches_observed: int
    matches_with_known_result: int
    wins: int
    losses: int
    updated_at: datetime
