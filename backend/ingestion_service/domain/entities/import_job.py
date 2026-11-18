from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ImportJob:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    source_snapshot: str
    status: str
    requested_by: UUID
    accepted_count: int
    rejected_count: int
    checkpoint: str | None
