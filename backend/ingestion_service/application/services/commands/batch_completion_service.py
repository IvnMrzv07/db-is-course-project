from __future__ import annotations

from dataclasses import dataclass
from contracts.messages import BatchCompleted
from ingestion_service.application.repositories.import_job_repository import ImportJobRepository
from ingestion_service.application.repositories.replay_job_repository import ReplayJobRepository
from ingestion_service.application.ports.unit_of_work import UnitOfWork


@dataclass(kw_only=True)
class BatchCompletionService:
    """Routes committed owner outcomes by job kind and applies each receipt once."""

    imports: ImportJobRepository
    replays: ReplayJobRepository
    unit_of_work: UnitOfWork

    async def handle(self, event: BatchCompleted) -> None:
        raise NotImplementedError("Validate owner/job, deduplicate receipt and update correct job")
