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
from ingestion_service.application.services.commands.import_service import ImportService


@dataclass(kw_only=True)
class ImportServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: ImportService

    async def start(self, command: StartImportDTO) -> JobProgressDTO:
        """Persist job and durable scheduling request; return job ID"""
        raise NotImplementedError("Persist job and durable scheduling request; return job ID")

    async def process_batch(self, job_id: UUID) -> None:
        """Validate identities and stage idempotent owner command"""
        raise NotImplementedError("Validate identities and stage idempotent owner command")

    async def complete_batch(self, event: BatchCompleted) -> None:
        """Apply durable owner result once and advance checkpoint"""
        raise NotImplementedError("Apply durable owner result once and advance checkpoint")
