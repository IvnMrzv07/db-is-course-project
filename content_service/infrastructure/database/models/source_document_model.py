from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SourceDocumentModel:
    """Persistence shape stub; no ORM/driver mapping configured."""

    id: UUID
    title: str
    text: str
    corpus_scope: str
    revision: int
