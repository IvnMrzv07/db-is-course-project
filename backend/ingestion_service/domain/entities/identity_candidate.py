from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class IdentityCandidate:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    provider: str
    external_id: str
    entity_type: str
    candidate_internal_ids: tuple[UUID, ...]
    review_status: str
