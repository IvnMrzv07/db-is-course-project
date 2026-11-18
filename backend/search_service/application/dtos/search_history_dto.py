from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SearchHistoryDTO:
    """Typed application boundary data."""

    query: str
    corpus_scope: str
    status: str
    result_count: int
    duration_ms: float
    cache_hit: bool
    occurred_at: datetime
