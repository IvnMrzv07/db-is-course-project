from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SearchableDocument:
    """Derived public/demo search projection with per-owner version bookkeeping."""

    entity_id: UUID
    entity_type: str
    title: str
    text: str
    language: str
    corpus_scope: str
    is_public: bool
    competition_version: int | None
    content_version: int | None
