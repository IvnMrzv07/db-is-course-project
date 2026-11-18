from __future__ import annotations

from uuid import UUID
from content_service.domain.entities.highlight import Highlight
from content_service.application.repositories.highlight_repository import HighlightRepository


class MongoHighlightRepository(HighlightRepository):
    """Mongo adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: Highlight) -> Highlight:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> Highlight | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[Highlight, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: Highlight, *, expected_version: int) -> Highlight:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
