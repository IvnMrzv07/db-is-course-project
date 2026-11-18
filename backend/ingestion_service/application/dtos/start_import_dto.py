from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class StartImportDTO:
    """Typed application boundary data."""

    snapshot_path: str
    actor_id: UUID
    idempotency_key: str
