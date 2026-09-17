from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.match_commands import CreateMatch, UpdateMatch
from competition_service.application.dtos.match_dto import MatchDTO
from competition_service.application.repositories.match_repository import MatchRepository
from competition_service.application.ports.unit_of_work import UnitOfWork


class MatchCommandService:
    """Authorize actor, validate domain state, and atomically persist changes/outbox."""

    def __init__(self, repository: MatchRepository, unit_of_work: UnitOfWork) -> None:
        self.repository = repository
        self.unit_of_work = unit_of_work

    async def create(self, command: CreateMatch) -> MatchDTO:
        raise NotImplementedError("Authorize, validate, create, stage event, commit")

    async def update(self, command: UpdateMatch) -> MatchDTO:
        raise NotImplementedError("Authorize, validate version and replacement, commit")

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        raise NotImplementedError("Authorize and apply versioned removal policy")
