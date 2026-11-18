from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from decimal import Decimal

@dataclass(frozen=True, kw_only=True)
class TournamentDTO:
    """Application response; no driver or HTTP types."""

    id: UUID
    version: int
    name: str
    discipline: str
    starts_at: datetime | None
    ends_at: datetime | None
    host_country: str | None
    prize_pool_amount: Decimal | None
    prize_pool_currency: str | None
    winner_team_id: UUID | None
    twitch_url: str | None
