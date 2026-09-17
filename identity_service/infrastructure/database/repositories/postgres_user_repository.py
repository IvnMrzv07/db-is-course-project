from __future__ import annotations

from uuid import UUID
from identity_service.domain.entities.user import User
from identity_service.application.repositories.user_repository import UserRepository


class PostgresUserRepository(UserRepository):
    """Postgres adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: User) -> User:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> User | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[User, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: User, *, expected_version: int) -> User:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
