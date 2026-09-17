from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from ingestion_service.application.ports.metadata_provider import MetadataProvider
from ingestion_service.application.repositories.enrichment_job_repository import EnrichmentJobRepository
from ingestion_service.application.repositories.identity_candidate_repository import IdentityCandidateRepository
from ingestion_service.application.ports.unit_of_work import UnitOfWork


@dataclass(kw_only=True)
class EnrichmentService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    provider: MetadataProvider
    jobs: EnrichmentJobRepository
    candidates: IdentityCandidateRepository
    unit_of_work: UnitOfWork

    async def start(self, actor_id: UUID, entity_ids: tuple[UUID, ...]) -> UUID:
        """Persist enrichment job for configured provider"""
        raise NotImplementedError("Persist enrichment job for configured provider")

    async def process(self, job_id: UUID) -> None:
        """Retrieve metadata, resolve candidates and submit changes to owners"""
        raise NotImplementedError("Retrieve metadata, resolve candidates and submit changes to owners")
