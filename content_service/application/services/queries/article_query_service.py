from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.article_dto import ArticleDTO
from content_service.application.repositories.article_repository import ArticleRepository


class ArticleQueryService:
    """Read use cases; enforce visibility before returning a DTO."""

    def __init__(self, repository: ArticleRepository) -> None:
        self.repository = repository

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> ArticleDTO | None:
        raise NotImplementedError("Visibility-aware read and DTO mapping")

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[ArticleDTO, ...]:
        raise NotImplementedError("Filtered bounded query")
