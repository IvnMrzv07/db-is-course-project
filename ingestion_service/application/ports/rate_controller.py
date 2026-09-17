from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol


class RateController(Protocol):
    """Outbound port owned by this application."""

    async def set_rate(self, job_id: UUID, documents_per_second: int) -> None:
        """Apply bounded target rate without restarting"""
        ...

    async def acquire(self, job_id: UUID, documents: int) -> None:
        """Wait asynchronously for per-job production allowance"""
        ...

    async def pause(self, job_id: UUID) -> None:
        """Pause new production while preserving existing queued work"""
        ...
