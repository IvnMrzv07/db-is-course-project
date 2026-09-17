from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ExternalIdentity:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    provider: str
    entity_type: str
    external_id: str
    internal_id: UUID
    verified_at: datetime
