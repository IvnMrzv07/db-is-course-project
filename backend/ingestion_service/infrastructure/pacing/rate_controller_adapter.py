from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol


@dataclass(kw_only=True)
class AsyncioRateController:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def set_rate(self, job_id: UUID, documents_per_second: int) -> None:
        """Apply bounded target rate without restarting"""
        raise NotImplementedError("Apply bounded target rate without restarting")

    async def acquire(self, job_id: UUID, documents: int) -> None:
        """Wait asynchronously for per-job production allowance"""
        raise NotImplementedError("Wait asynchronously for per-job production allowance")

    async def pause(self, job_id: UUID) -> None:
        """Pause new production while preserving existing queued work"""
        raise NotImplementedError("Pause new production while preserving existing queued work")
