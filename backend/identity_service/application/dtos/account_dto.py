from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class AccountDTO:
    """Typed application boundary data."""

    id: UUID
    email: str
    display_name: str
    roles: tuple[str, ...]
    version: int
