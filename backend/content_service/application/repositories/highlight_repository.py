from __future__ import annotations

from content_service.domain.entities.highlight import Highlight
from .crud_repository import CrudRepository
from typing import Protocol


class HighlightRepository(CrudRepository[Highlight], Protocol):
    """CRUD port for locally owned Highlight records."""
