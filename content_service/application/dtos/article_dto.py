from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ArticleDTO:
    """Application response; no driver or HTTP types."""

    id: UUID
    version: int
    title: str
    body: str
    match_id: UUID | None
    author_id: UUID
    publication_status: str
    source_urls: tuple[str, ...]
    is_generated: bool
