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


@dataclass(kw_only=True)
class ReplayQueryService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    jobs: ReplayJobRepository

    async def get_progress(self, job_id: UUID, actor_id: UUID) -> JobProgressDTO:
        """Read actual persisted progress independently of requested rate"""
        raise NotImplementedError("Read actual persisted progress independently of requested rate")
