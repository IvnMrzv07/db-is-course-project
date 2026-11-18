from __future__ import annotations

from identity_service.domain.entities.user import User
from .crud_repository import CrudRepository
from typing import Protocol


class UserRepository(CrudRepository[User], Protocol):
    """CRUD port for locally owned User records."""
