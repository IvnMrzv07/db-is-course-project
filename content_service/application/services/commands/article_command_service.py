from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.article_commands import CreateArticle, UpdateArticle
from content_service.application.dtos.article_dto import ArticleDTO
from content_service.application.repositories.article_repository import ArticleRepository
from content_service.application.ports.unit_of_work import UnitOfWork


class ArticleCommandService:
    """Authorize actor, validate domain state, and atomically persist changes/outbox."""

    def __init__(self, repository: ArticleRepository, unit_of_work: UnitOfWork) -> None:
        self.repository = repository
        self.unit_of_work = unit_of_work

    async def create(self, command: CreateArticle) -> ArticleDTO:
        raise NotImplementedError("Authorize, validate, create, stage event, commit")

    async def update(self, command: UpdateArticle) -> ArticleDTO:
        raise NotImplementedError("Authorize, validate version and replacement, commit")

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        raise NotImplementedError("Authorize and apply versioned removal policy")
