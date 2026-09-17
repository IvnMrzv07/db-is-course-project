from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class CorpusStatisticsDTO:
    """Typed application boundary data."""

    corpus_scope: str
    stored_documents: int
    durable_documents_per_second: float
    sampled_at: datetime
    indexed_documents: int | None
