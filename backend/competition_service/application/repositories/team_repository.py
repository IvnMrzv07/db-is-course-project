from __future__ import annotations

from competition_service.domain.entities.team import Team
from .crud_repository import CrudRepository
from typing import Protocol


class TeamRepository(CrudRepository[Team], Protocol):
    """CRUD port for locally owned Team records."""
