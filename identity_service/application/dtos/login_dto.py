from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class LoginDTO:
    """Typed application boundary data."""

    email: str
    password: str
