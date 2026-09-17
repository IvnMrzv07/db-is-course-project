from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SourceDocument:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    title: str
    text: str
    language: str
    provider: str
    source_id: str
    source_url: str | None
    retrieved_at: datetime
    corpus_scope: str
    is_synthetic: bool
    publication_status: str
    related_entity_ids: tuple[UUID, ...]
    metadata: dict[str, str]
