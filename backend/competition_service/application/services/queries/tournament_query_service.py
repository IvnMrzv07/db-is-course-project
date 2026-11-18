from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.tournament_dto import TournamentDTO
from competition_service.application.repositories.tournament_repository import TournamentRepository


class TournamentQueryService:
    """Read use cases; enforce visibility before returning a DTO."""

    def __init__(self, repository: TournamentRepository) -> None:
        self.repository = repository

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> TournamentDTO | None:
        raise NotImplementedError("Visibility-aware read and DTO mapping")

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[TournamentDTO, ...]:
        raise NotImplementedError("Filtered bounded query")
