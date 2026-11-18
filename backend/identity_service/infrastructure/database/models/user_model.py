from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class UserModel:
    """Persistence shape stub; no ORM/driver mapping configured."""

    id: UUID
    email: str
    password_hash: str
    is_active: bool
