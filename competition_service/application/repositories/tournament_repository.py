from __future__ import annotations

from competition_service.domain.entities.tournament import Tournament
from .crud_repository import CrudRepository
from typing import Protocol


class TournamentRepository(CrudRepository[Tournament], Protocol):
    """CRUD port for locally owned Tournament records."""
