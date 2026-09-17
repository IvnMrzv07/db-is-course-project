from __future__ import annotations

from ingestion_service.domain.entities.identity_candidate import IdentityCandidate
from .crud_repository import CrudRepository
from typing import Protocol


class IdentityCandidateRepository(CrudRepository[IdentityCandidate], Protocol):
    """CRUD port for locally owned IdentityCandidate records."""
