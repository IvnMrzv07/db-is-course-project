from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class PlayerRequest:
    """Untrusted request body; does not contain the authenticated actor ID."""

    nickname: str
    real_name: str | None
    country_code: str | None
    role: str | None
