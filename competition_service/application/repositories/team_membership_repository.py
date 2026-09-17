from __future__ import annotations

from competition_service.domain.entities.team_membership import TeamMembership
from .crud_repository import CrudRepository
from typing import Protocol


class TeamMembershipRepository(CrudRepository[TeamMembership], Protocol):
    """CRUD port for locally owned TeamMembership records."""
