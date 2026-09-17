from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ComparisonQuery:
    """Typed application boundary data."""

    team1_id: UUID
    team2_id: UUID
    starts_at: datetime
    ends_at: datetime
    map_name: str | None = None
