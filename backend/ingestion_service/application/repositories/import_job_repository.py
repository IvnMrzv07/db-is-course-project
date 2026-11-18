from __future__ import annotations

from ingestion_service.domain.entities.import_job import ImportJob
from .crud_repository import CrudRepository
from typing import Protocol


class ImportJobRepository(CrudRepository[ImportJob], Protocol):
    """CRUD port for locally owned ImportJob records."""
