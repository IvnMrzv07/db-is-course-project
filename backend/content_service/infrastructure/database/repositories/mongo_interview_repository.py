from __future__ import annotations

from uuid import UUID
from content_service.domain.entities.interview import Interview
from content_service.application.repositories.interview_repository import InterviewRepository


class MongoInterviewRepository(InterviewRepository):
    """Mongo adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: Interview) -> Interview:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> Interview | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[Interview, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: Interview, *, expected_version: int) -> Interview:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
