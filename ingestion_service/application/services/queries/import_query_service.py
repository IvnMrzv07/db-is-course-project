from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from ingestion_service.application.dtos.start_import_dto import StartImportDTO
from ingestion_service.application.dtos.job_progress_dto import JobProgressDTO
from ingestion_service.application.repositories.import_job_repository import ImportJobRepository
from ingestion_service.application.ports.dataset_reader import DatasetReader
from ingestion_service.application.ports.command_publisher import CommandPublisher
from ingestion_service.application.ports.unit_of_work import UnitOfWork
from contracts.messages import BatchCompleted


@dataclass(kw_only=True)
class ImportQueryService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    jobs: ImportJobRepository

    async def get_progress(self, job_id: UUID, actor_id: UUID) -> JobProgressDTO:
        """Authorize and read persisted job progress"""
        raise NotImplementedError("Authorize and read persisted job progress")
