from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.player_commands import CreatePlayer, UpdatePlayer
from competition_service.application.dtos.player_dto import PlayerDTO
from competition_service.application.repositories.player_repository import PlayerRepository
from competition_service.application.ports.unit_of_work import UnitOfWork


class PlayerCommandService:
    """Authorize actor, validate domain state, and atomically persist changes/outbox."""

    def __init__(self, repository: PlayerRepository, unit_of_work: UnitOfWork) -> None:
        self.repository = repository
        self.unit_of_work = unit_of_work

    async def create(self, command: CreatePlayer) -> PlayerDTO:
        raise NotImplementedError("Authorize, validate, create, stage event, commit")

    async def update(self, command: UpdatePlayer) -> PlayerDTO:
        raise NotImplementedError("Authorize, validate version and replacement, commit")

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        raise NotImplementedError("Authorize and apply versioned removal policy")
