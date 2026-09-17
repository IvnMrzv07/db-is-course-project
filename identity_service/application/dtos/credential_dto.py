from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class CredentialDTO:
    """Typed application boundary data."""

    opaque_credential: str
    expires_at: datetime
