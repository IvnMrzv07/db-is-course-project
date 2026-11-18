from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from identity_service.application.dtos.bookmark_dto import BookmarkDTO
from identity_service.application.repositories.bookmark_repository import BookmarkRepository
from identity_service.application.ports.unit_of_work import UnitOfWork
from identity_service.application.services.queries.bookmark_query_service import BookmarkQueryService


@dataclass(kw_only=True)
class BookmarkQueryServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: BookmarkQueryService

    async def list_mine(self, actor_id: UUID, limit: int = 50, offset: int = 0) -> tuple[BookmarkDTO, ...]:
        """Return only the authenticated users bookmarks"""
        raise NotImplementedError("Return only the authenticated users bookmarks")
