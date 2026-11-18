from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SearchHitDTO:
    """Typed application boundary data."""

    entity_id: UUID
    entity_type: str
    title: str
    snippet: str
    highlights: tuple[str, ...]
    score: float
    source_version: int
