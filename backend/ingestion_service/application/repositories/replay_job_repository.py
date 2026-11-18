from __future__ import annotations

from ingestion_service.domain.entities.replay_job import ReplayJob
from .crud_repository import CrudRepository
from typing import Protocol


class ReplayJobRepository(CrudRepository[ReplayJob], Protocol):
    """CRUD port for locally owned ReplayJob records."""
