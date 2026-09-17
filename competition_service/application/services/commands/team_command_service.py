from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.team_commands import CreateTeam, UpdateTeam
from competition_service.application.dtos.team_dto import TeamDTO
from competition_service.application.repositories.team_repository import TeamRepository
from competition_service.application.ports.unit_of_work import UnitOfWork


class TeamCommandService:
    """Authorize actor, validate domain state, and atomically persist changes/outbox."""

    def __init__(self, repository: TeamRepository, unit_of_work: UnitOfWork) -> None:
        self.repository = repository
        self.unit_of_work = unit_of_work

    async def create(self, command: CreateTeam) -> TeamDTO:
        raise NotImplementedError("Authorize, validate, create, stage event, commit")

    async def update(self, command: UpdateTeam) -> TeamDTO:
        raise NotImplementedError("Authorize, validate version and replacement, commit")

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        raise NotImplementedError("Authorize and apply versioned removal policy")
