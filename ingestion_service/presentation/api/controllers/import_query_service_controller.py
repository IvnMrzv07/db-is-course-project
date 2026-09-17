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
from ingestion_service.application.services.queries.import_query_service import ImportQueryService


@dataclass(kw_only=True)
class ImportQueryServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: ImportQueryService

    async def get_progress(self, job_id: UUID, actor_id: UUID) -> JobProgressDTO:
        """Authorize and read persisted job progress"""
        raise NotImplementedError("Authorize and read persisted job progress")
