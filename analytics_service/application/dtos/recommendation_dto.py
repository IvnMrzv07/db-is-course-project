from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class RecommendationDTO:
    """Typed application boundary data."""

    match_id: UUID
    reason: str
    rank: int
