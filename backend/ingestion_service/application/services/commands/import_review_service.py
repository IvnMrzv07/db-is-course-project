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
class ImportReviewService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    candidates: IdentityCandidateRepository
    unit_of_work: UnitOfWork

    async def resolve(self, candidate_id: UUID, internal_id: UUID, actor_id: UUID) -> None:
        """Record review and propose accepted mapping to Competition owner"""
        raise NotImplementedError("Record review and propose accepted mapping to Competition owner")
