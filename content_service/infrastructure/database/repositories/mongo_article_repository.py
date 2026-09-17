from __future__ import annotations

from uuid import UUID
from content_service.domain.entities.article import Article
from content_service.application.repositories.article_repository import ArticleRepository


class MongoArticleRepository(ArticleRepository):
    """Mongo adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: Article) -> Article:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> Article | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[Article, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: Article, *, expected_version: int) -> Article:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
