from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ReplayJob:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    source_snapshot: str
    corpus_scope: str
    status: str
    target_documents_per_second: int
    attempted_count: int
    stored_count: int
    checkpoint: str | None
