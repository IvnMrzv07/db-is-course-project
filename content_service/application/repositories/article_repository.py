from __future__ import annotations

from content_service.domain.entities.article import Article
from .crud_repository import CrudRepository
from typing import Protocol


class ArticleRepository(CrudRepository[Article], Protocol):
    """CRUD port for locally owned Article records."""
