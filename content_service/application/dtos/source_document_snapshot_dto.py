from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SourceDocumentSnapshotDTO:
    """Eligible snapshot or versioned tombstone; text is absent when not indexable."""

    id: UUID
    version: int
    title: str | None
    text: str | None
    language: str
    corpus_scope: str
    indexable: bool
    updated_at: datetime
