from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class CreateArticle:
    """Creation input; authorization and idempotency must be checked by the command service."""

    title: str
    body: str
    match_id: UUID | None
    author_id: UUID
    publication_status: str
    source_urls: tuple[str, ...]
    is_generated: bool
    actor_id: UUID
    idempotency_key: str


@dataclass(frozen=True, kw_only=True)
class UpdateArticle:
    """Full replacement; explicit null values clear nullable fields."""

    id: UUID
    expected_version: int
    title: str
    body: str
    match_id: UUID | None
    author_id: UUID
    publication_status: str
    source_urls: tuple[str, ...]
    is_generated: bool
    actor_id: UUID
