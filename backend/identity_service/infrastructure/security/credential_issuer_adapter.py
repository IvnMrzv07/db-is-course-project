from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from identity_service.application.dtos.credential_dto import CredentialDTO


@dataclass(kw_only=True)
class CredentialIssuerAdapter:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def issue(self, user_id: UUID) -> CredentialDTO:
        """Create opaque credential; cookie/token transport still undecided"""
        raise NotImplementedError("Create opaque credential; cookie/token transport still undecided")

    async def revoke(self, credential: str) -> None:
        """Revoke active credential"""
        raise NotImplementedError("Revoke active credential")
