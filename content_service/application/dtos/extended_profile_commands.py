from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class CreateExtendedProfile:
    """Creation input; authorization and idempotency must be checked by the command service."""

    player_id: UUID
    biography: str
    play_style_tags: tuple[str, ...]
    source_urls: tuple[str, ...]
    publication_status: str
    actor_id: UUID
    idempotency_key: str


@dataclass(frozen=True, kw_only=True)
class UpdateExtendedProfile:
    """Full replacement; explicit null values clear nullable fields."""

    id: UUID
    expected_version: int
    player_id: UUID
    biography: str
    play_style_tags: tuple[str, ...]
    source_urls: tuple[str, ...]
    publication_status: str
    actor_id: UUID
