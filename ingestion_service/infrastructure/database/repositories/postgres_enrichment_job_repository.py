from __future__ import annotations

from uuid import UUID
from ingestion_service.domain.entities.enrichment_job import EnrichmentJob
from ingestion_service.application.repositories.enrichment_job_repository import EnrichmentJobRepository


class PostgresEnrichmentJobRepository(EnrichmentJobRepository):
    """Postgres adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: EnrichmentJob) -> EnrichmentJob:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> EnrichmentJob | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[EnrichmentJob, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: EnrichmentJob, *, expected_version: int) -> EnrichmentJob:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
