from __future__ import annotations

from competition_service.domain.entities.player import Player
from .crud_repository import CrudRepository
from typing import Protocol


class PlayerRepository(CrudRepository[Player], Protocol):
    """CRUD port for locally owned Player records."""
