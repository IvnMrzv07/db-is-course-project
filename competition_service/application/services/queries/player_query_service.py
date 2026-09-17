from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.player_dto import PlayerDTO
from competition_service.application.repositories.player_repository import PlayerRepository


class PlayerQueryService:
    """Read use cases; enforce visibility before returning a DTO."""

    def __init__(self, repository: PlayerRepository) -> None:
        self.repository = repository

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> PlayerDTO | None:
        raise NotImplementedError("Visibility-aware read and DTO mapping")

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[PlayerDTO, ...]:
        raise NotImplementedError("Filtered bounded query")
