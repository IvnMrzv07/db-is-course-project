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
class ImportService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    jobs: ImportJobRepository
    reader: DatasetReader
    publisher: CommandPublisher
    unit_of_work: UnitOfWork

    async def start(self, command: StartImportDTO) -> JobProgressDTO:
        """Persist job and durable scheduling request; return job ID"""
        raise NotImplementedError("Persist job and durable scheduling request; return job ID")

    async def process_batch(self, job_id: UUID) -> None:
        """Validate identities and stage idempotent owner command"""
        raise NotImplementedError("Validate identities and stage idempotent owner command")

    async def complete_batch(self, event: BatchCompleted) -> None:
        """Apply durable owner result once and advance checkpoint"""
        raise NotImplementedError("Apply durable owner result once and advance checkpoint")
