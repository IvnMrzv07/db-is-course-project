from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class CreateInterview:
    """Creation input; authorization and idempotency must be checked by the command service."""

    player_id: UUID
    title: str
    questions_and_answers: tuple[tuple[str, str], ...]
    source_url: str
    publication_status: str
    actor_id: UUID
    idempotency_key: str


@dataclass(frozen=True, kw_only=True)
class UpdateInterview:
    """Full replacement; explicit null values clear nullable fields."""

    id: UUID
    expected_version: int
    player_id: UUID
    title: str
    questions_and_answers: tuple[tuple[str, str], ...]
    source_url: str
    publication_status: str
    actor_id: UUID
