from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .search_hit_dto import SearchHitDTO

@dataclass(frozen=True, kw_only=True)
class SearchResultDTO:
    """Typed application boundary data."""

    hits: tuple[SearchHitDTO, ...]
    total: int
    index_generation: str
    updated_at: datetime
