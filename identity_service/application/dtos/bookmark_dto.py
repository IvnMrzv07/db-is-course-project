from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class BookmarkDTO:
    """Typed application boundary data."""

    id: UUID
    target_type: str
    target_id: UUID
    version: int
