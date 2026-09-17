from __future__ import annotations

from competition_service.domain.entities.match_lineup import MatchLineup
from .crud_repository import CrudRepository
from typing import Protocol


class MatchLineupRepository(CrudRepository[MatchLineup], Protocol):
    """CRUD port for locally owned MatchLineup records."""
