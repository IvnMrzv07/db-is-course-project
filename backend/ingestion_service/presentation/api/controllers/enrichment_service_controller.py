from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from ingestion_service.application.ports.metadata_provider import MetadataProvider
from ingestion_service.application.repositories.enrichment_job_repository import EnrichmentJobRepository
from ingestion_service.application.repositories.identity_candidate_repository import IdentityCandidateRepository
from ingestion_service.application.ports.unit_of_work import UnitOfWork
from ingestion_service.application.services.commands.enrichment_service import EnrichmentService


@dataclass(kw_only=True)
class EnrichmentServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: EnrichmentService

    async def start(self, actor_id: UUID, entity_ids: tuple[UUID, ...]) -> UUID:
        """Persist enrichment job for configured provider"""
        raise NotImplementedError("Persist enrichment job for configured provider")

    async def process(self, job_id: UUID) -> None:
        """Retrieve metadata, resolve candidates and submit changes to owners"""
        raise NotImplementedError("Retrieve metadata, resolve candidates and submit changes to owners")
