from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from identity_service.application.dtos.credential_dto import CredentialDTO


class CredentialIssuer(Protocol):
    """Outbound port owned by this application."""

    async def issue(self, user_id: UUID) -> CredentialDTO:
        """Create opaque credential; cookie/token transport still undecided"""
        ...

    async def revoke(self, credential: str) -> None:
        """Revoke active credential"""
        ...
