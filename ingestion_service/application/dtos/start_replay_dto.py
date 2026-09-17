from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class StartReplayDTO:
    """Typed application boundary data."""

    snapshot_path: str
    corpus_scope: str
    target_documents_per_second: int
    actor_id: UUID
    idempotency_key: str
