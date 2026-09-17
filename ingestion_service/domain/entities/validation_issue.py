from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ValidationIssue:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    job_id: UUID
    source_record_id: str
    reason: str
    status: str
