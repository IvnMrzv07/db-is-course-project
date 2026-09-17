from __future__ import annotations

from competition_service.domain.entities.match import Match
from .crud_repository import CrudRepository
from typing import Protocol


class MatchRepository(CrudRepository[Match], Protocol):
    """CRUD port for locally owned Match records."""
