from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.highlight_dto import HighlightDTO
from content_service.application.repositories.highlight_repository import HighlightRepository


class HighlightQueryService:
    """Read use cases; enforce visibility before returning a DTO."""

    def __init__(self, repository: HighlightRepository) -> None:
        self.repository = repository

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> HighlightDTO | None:
        raise NotImplementedError("Visibility-aware read and DTO mapping")

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[HighlightDTO, ...]:
        raise NotImplementedError("Filtered bounded query")
