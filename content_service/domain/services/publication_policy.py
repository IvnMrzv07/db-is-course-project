from __future__ import annotations

from uuid import UUID
from ..entities.article import Article


class PublicationPolicy:
    """Pure domain policy stub; does not perform I/O."""

    def validate(self, article: Article) -> None:
        raise NotImplementedError("Implement domain rules")
