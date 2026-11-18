from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class TeamComparisonDTO:
    """Typed application boundary data."""

    team1_id: UUID
    team2_id: UUID
    head_to_head_matches: int
    team1_wins: int
    team2_wins: int
    team1_overall_win_rate: float | None
    team2_overall_win_rate: float | None
    coverage_note: str
    updated_at: datetime
