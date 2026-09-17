from __future__ import annotations

from content_service.domain.entities.article import Article
from content_service.application.dtos.article_dto import ArticleDTO


class ArticleDTOMapper:
    """Maps domain values into the application response representation."""

    @staticmethod
    def to_dto(entity: Article) -> ArticleDTO:
        raise NotImplementedError("Explicit field mapping")
