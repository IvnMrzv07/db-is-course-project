from __future__ import annotations

from uuid import UUID
from competition_service.domain.entities.team_membership import TeamMembership
from competition_service.application.repositories.team_membership_repository import TeamMembershipRepository


class PostgresTeamMembershipRepository(TeamMembershipRepository):
    """Postgres adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: TeamMembership) -> TeamMembership:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> TeamMembership | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[TeamMembership, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: TeamMembership, *, expected_version: int) -> TeamMembership:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
