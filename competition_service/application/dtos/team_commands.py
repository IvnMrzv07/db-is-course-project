from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class CreateTeam:
    """Creation input; authorization and idempotency must be checked by the command service."""

    name: str
    region: str | None
    founded_at: datetime | None
    actor_id: UUID
    idempotency_key: str


@dataclass(frozen=True, kw_only=True)
class UpdateTeam:
    """Full replacement; explicit null values clear nullable fields."""

    id: UUID
    expected_version: int
    name: str
    region: str | None
    founded_at: datetime | None
    actor_id: UUID
