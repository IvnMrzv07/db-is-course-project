from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class JobProgressDTO:
    """Typed application boundary data."""

    job_id: UUID
    status: str
    attempted: int
    accepted: int
    rejected: int
    checkpoint: str | None
    updated_at: datetime
