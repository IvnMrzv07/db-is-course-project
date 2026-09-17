from __future__ import annotations

from uuid import UUID
from competition_service.domain.entities.tournament import Tournament
from competition_service.application.repositories.tournament_repository import TournamentRepository


class PostgresTournamentRepository(TournamentRepository):
    """Postgres adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: Tournament) -> Tournament:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> Tournament | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[Tournament, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: Tournament, *, expected_version: int) -> Tournament:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
