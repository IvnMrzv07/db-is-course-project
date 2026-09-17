from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SearchQueryDTO:
    """Typed application boundary data."""

    text: str
    corpus_scope: str
    language: str
    mode: str = "keywords"
    filters: tuple[tuple[str, str], ...] = ()
    page: int = 1
    page_size: int = 20
    sort: str = "relevance"
