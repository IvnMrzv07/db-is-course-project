from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ImportJobModel:
    """Persistence shape stub; no ORM/driver mapping configured."""

    id: UUID
    source_snapshot: str
    status: str
    checkpoint: str | None
