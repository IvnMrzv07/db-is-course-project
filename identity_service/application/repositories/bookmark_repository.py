from __future__ import annotations

from identity_service.domain.entities.bookmark import Bookmark
from .crud_repository import CrudRepository
from typing import Protocol


class BookmarkRepository(CrudRepository[Bookmark], Protocol):
    """CRUD port for locally owned Bookmark records."""
