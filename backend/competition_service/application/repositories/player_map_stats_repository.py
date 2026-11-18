from __future__ import annotations

from competition_service.domain.entities.player_map_stats import PlayerMapStats
from .crud_repository import CrudRepository
from typing import Protocol


class PlayerMapStatsRepository(CrudRepository[PlayerMapStats], Protocol):
    """CRUD port for locally owned PlayerMapStats records."""
