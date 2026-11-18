from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Bookmark:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    user_id: UUID
    target_type: str
    target_id: UUID
