from __future__ import annotations

from uuid import UUID
from identity_service.domain.entities.bookmark import Bookmark
from identity_service.application.repositories.bookmark_repository import BookmarkRepository


class PostgresBookmarkRepository(BookmarkRepository):
    """Postgres adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: Bookmark) -> Bookmark:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> Bookmark | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[Bookmark, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: Bookmark, *, expected_version: int) -> Bookmark:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
