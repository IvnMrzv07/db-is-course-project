from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class User:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    email: str
    display_name: str
    password_hash: str
    roles: tuple[str, ...]
    is_active: bool
