from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.team_dto import TeamDTO
from competition_service.application.repositories.team_repository import TeamRepository


class TeamQueryService:
    """Read use cases; enforce visibility before returning a DTO."""

    def __init__(self, repository: TeamRepository) -> None:
        self.repository = repository

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> TeamDTO | None:
        raise NotImplementedError("Visibility-aware read and DTO mapping")

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[TeamDTO, ...]:
        raise NotImplementedError("Filtered bounded query")
