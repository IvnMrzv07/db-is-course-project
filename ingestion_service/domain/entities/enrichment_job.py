from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class EnrichmentJob:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    provider: str
    entity_ids: tuple[UUID, ...]
    status: str
    checkpoint: str | None
