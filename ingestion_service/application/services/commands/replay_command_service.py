from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from ingestion_service.application.dtos.start_replay_dto import StartReplayDTO
from ingestion_service.application.dtos.job_progress_dto import JobProgressDTO
from ingestion_service.application.repositories.replay_job_repository import ReplayJobRepository
from ingestion_service.application.ports.rate_controller import RateController
from ingestion_service.application.ports.unit_of_work import UnitOfWork
from ingestion_service.application.ports.dataset_reader import DatasetReader
from ingestion_service.application.ports.command_publisher import CommandPublisher


@dataclass(kw_only=True)
class ReplayCommandService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    jobs: ReplayJobRepository
    pacer: RateController
    reader: DatasetReader
    publisher: CommandPublisher
    unit_of_work: UnitOfWork

    async def start(self, command: StartReplayDTO) -> JobProgressDTO:
        """Validate isolated corpus and target rate, persist replay job"""
        raise NotImplementedError("Validate isolated corpus and target rate, persist replay job")

    async def change_rate(self, job_id: UUID, actor_id: UUID, documents_per_second: int) -> None:
        """Validate 10 to 5000 target, persist configuration and notify worker"""
        raise NotImplementedError("Validate 10 to 5000 target, persist configuration and notify worker")

    async def pause(self, job_id: UUID, actor_id: UUID) -> None:
        """Persist paused state and stop new production"""
        raise NotImplementedError("Persist paused state and stop new production")

    async def process_batch(self, job_id: UUID) -> None:
        """Read prepared corpus, await pacing, and stage an idempotent owner command."""
        raise NotImplementedError("Paced batch production; durability is reported by Content")
