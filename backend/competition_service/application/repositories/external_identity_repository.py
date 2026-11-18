from __future__ import annotations

from competition_service.domain.entities.external_identity import ExternalIdentity
from .crud_repository import CrudRepository
from typing import Protocol


class ExternalIdentityRepository(CrudRepository[ExternalIdentity], Protocol):
    """CRUD port for locally owned ExternalIdentity records."""
