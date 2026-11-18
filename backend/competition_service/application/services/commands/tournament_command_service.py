from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.tournament_commands import CreateTournament, UpdateTournament
from competition_service.application.dtos.tournament_dto import TournamentDTO
from competition_service.application.repositories.tournament_repository import TournamentRepository
from competition_service.application.ports.unit_of_work import UnitOfWork


class TournamentCommandService:
    """Authorize actor, validate domain state, and atomically persist changes/outbox."""

    def __init__(self, repository: TournamentRepository, unit_of_work: UnitOfWork) -> None:
        self.repository = repository
        self.unit_of_work = unit_of_work

    async def create(self, command: CreateTournament) -> TournamentDTO:
        raise NotImplementedError("Authorize, validate, create, stage event, commit")

    async def update(self, command: UpdateTournament) -> TournamentDTO:
        raise NotImplementedError("Authorize, validate version and replacement, commit")

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        raise NotImplementedError("Authorize and apply versioned removal policy")
