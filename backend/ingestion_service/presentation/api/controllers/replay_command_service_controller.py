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
from ingestion_service.application.services.commands.replay_command_service import ReplayCommandService


@dataclass(kw_only=True)
class ReplayCommandServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: ReplayCommandService

    async def start(self, command: StartReplayDTO) -> JobProgressDTO:
        """Validate isolated corpus and target rate, persist replay job"""
        raise NotImplementedError("Validate isolated corpus and target rate, persist replay job")

    async def change_rate(self, job_id: UUID, actor_id: UUID, documents_per_second: int) -> None:
        """Validate 10 to 5000 target, persist configuration and notify worker"""
        raise NotImplementedError("Validate 10 to 5000 target, persist configuration and notify worker")

    async def pause(self, job_id: UUID, actor_id: UUID) -> None:
        """Persist paused state and stop new production"""
        raise NotImplementedError("Persist paused state and stop new production")
