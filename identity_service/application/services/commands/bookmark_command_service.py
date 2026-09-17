from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from identity_service.application.dtos.bookmark_dto import BookmarkDTO
from identity_service.application.repositories.bookmark_repository import BookmarkRepository
from identity_service.application.ports.unit_of_work import UnitOfWork


@dataclass(kw_only=True)
class BookmarkCommandService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    bookmarks: BookmarkRepository
    unit_of_work: UnitOfWork

    async def add(self, actor_id: UUID, target_type: str, target_id: UUID) -> BookmarkDTO:
        """Validate target and enforce uniqueness for user/type/target"""
        raise NotImplementedError("Validate target and enforce uniqueness for user/type/target")

    async def remove(self, actor_id: UUID, bookmark_id: UUID, expected_version: int) -> None:
        """Enforce ownership and delete"""
        raise NotImplementedError("Enforce ownership and delete")
