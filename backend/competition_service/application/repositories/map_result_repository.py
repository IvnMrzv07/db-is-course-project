from __future__ import annotations

from competition_service.domain.entities.map_result import MapResult
from .crud_repository import CrudRepository
from typing import Protocol


class MapResultRepository(CrudRepository[MapResult], Protocol):
    """CRUD port for locally owned MapResult records."""
