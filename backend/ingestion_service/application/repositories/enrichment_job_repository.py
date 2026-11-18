from __future__ import annotations

from ingestion_service.domain.entities.enrichment_job import EnrichmentJob
from .crud_repository import CrudRepository
from typing import Protocol


class EnrichmentJobRepository(CrudRepository[EnrichmentJob], Protocol):
    """CRUD port for locally owned EnrichmentJob records."""
