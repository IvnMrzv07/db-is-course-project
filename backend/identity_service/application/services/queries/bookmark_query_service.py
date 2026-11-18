from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from identity_service.application.dtos.bookmark_dto import BookmarkDTO
from identity_service.application.repositories.bookmark_repository import BookmarkRepository
from identity_service.application.ports.unit_of_work import UnitOfWork


@dataclass(kw_only=True)
class BookmarkQueryService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    bookmarks: BookmarkRepository

    async def list_mine(self, actor_id: UUID, limit: int = 50, offset: int = 0) -> tuple[BookmarkDTO, ...]:
        """Return only the authenticated users bookmarks"""
        raise NotImplementedError("Return only the authenticated users bookmarks")
