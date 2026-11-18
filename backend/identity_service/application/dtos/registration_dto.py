from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class RegistrationDTO:
    """Typed application boundary data."""

    email: str
    display_name: str
    password: str
