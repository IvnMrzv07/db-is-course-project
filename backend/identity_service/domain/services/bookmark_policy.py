from __future__ import annotations

from uuid import UUID
from ..entities.bookmark import Bookmark


class BookmarkPolicy:
    """Pure domain policy stub; does not perform I/O."""

    def validate(self, bookmark: Bookmark, actor_id: UUID) -> None:
        raise NotImplementedError("Implement domain rules")
