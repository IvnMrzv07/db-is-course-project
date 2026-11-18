from __future__ import annotations

from uuid import UUID
from ingestion_service.domain.entities.import_job import ImportJob
from ingestion_service.application.repositories.import_job_repository import ImportJobRepository


class PostgresImportJobRepository(ImportJobRepository):
    """Postgres adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: ImportJob) -> ImportJob:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> ImportJob | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[ImportJob, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: ImportJob, *, expected_version: int) -> ImportJob:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
