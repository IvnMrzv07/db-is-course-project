from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Player:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    nickname: str
    real_name: str | None
    country_code: str | None
    role: str | None
