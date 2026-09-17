from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.match_dto import MatchDTO
from competition_service.application.repositories.match_repository import MatchRepository


class MatchQueryService:
    """Read use cases; enforce visibility before returning a DTO."""

    def __init__(self, repository: MatchRepository) -> None:
        self.repository = repository

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> MatchDTO | None:
        raise NotImplementedError("Visibility-aware read and DTO mapping")

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[MatchDTO, ...]:
        raise NotImplementedError("Filtered bounded query")
