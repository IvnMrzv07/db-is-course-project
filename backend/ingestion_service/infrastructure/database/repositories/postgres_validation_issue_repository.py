from __future__ import annotations

from uuid import UUID
from ingestion_service.domain.entities.validation_issue import ValidationIssue
from ingestion_service.application.repositories.validation_issue_repository import ValidationIssueRepository


class PostgresValidationIssueRepository(ValidationIssueRepository):
    """Postgres adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: ValidationIssue) -> ValidationIssue:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> ValidationIssue | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[ValidationIssue, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: ValidationIssue, *, expected_version: int) -> ValidationIssue:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
