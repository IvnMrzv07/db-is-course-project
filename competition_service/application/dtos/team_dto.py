from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class TeamDTO:
    """Application response; no driver or HTTP types."""

    id: UUID
    version: int
    name: str
    region: str | None
    founded_at: datetime | None
