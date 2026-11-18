from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class CreatePlayer:
    """Creation input; authorization and idempotency must be checked by the command service."""

    nickname: str
    real_name: str | None
    country_code: str | None
    role: str | None
    actor_id: UUID
    idempotency_key: str


@dataclass(frozen=True, kw_only=True)
class UpdatePlayer:
    """Full replacement; explicit null values clear nullable fields."""

    id: UUID
    expected_version: int
    nickname: str
    real_name: str | None
    country_code: str | None
    role: str | None
    actor_id: UUID
