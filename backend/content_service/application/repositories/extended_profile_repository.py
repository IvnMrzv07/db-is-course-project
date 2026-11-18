from __future__ import annotations

from content_service.domain.entities.extended_profile import ExtendedProfile
from .crud_repository import CrudRepository
from typing import Protocol


class ExtendedProfileRepository(CrudRepository[ExtendedProfile], Protocol):
    """CRUD port for locally owned ExtendedProfile records."""
