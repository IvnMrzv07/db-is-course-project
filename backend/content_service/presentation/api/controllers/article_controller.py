from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.article_commands import CreateArticle, UpdateArticle
from content_service.application.dtos.article_dto import ArticleDTO
from content_service.application.services.commands.article_command_service import ArticleCommandService
from content_service.application.services.queries.article_query_service import ArticleQueryService


class ArticleController:
    """HTTP adapter skeleton; trusted actor IDs come from authentication, not request JSON.

    FastAPI route registration, schema conversion, error mapping and auth are pending.
    """

    def __init__(self, commands: ArticleCommandService, queries: ArticleQueryService) -> None:
        self.commands = commands
        self.queries = queries

    async def create(self, command: CreateArticle) -> ArticleDTO:
        return await self.commands.create(command)

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> ArticleDTO | None:
        return await self.queries.get(entity_id, viewer_id=viewer_id)

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[ArticleDTO, ...]:
        return await self.queries.list(viewer_id=viewer_id, limit=limit, offset=offset)

    async def update(self, command: UpdateArticle) -> ArticleDTO:
        return await self.commands.update(command)

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        await self.commands.delete(entity_id, actor_id=actor_id, expected_version=expected_version)
