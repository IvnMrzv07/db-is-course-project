from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import ChangeNotification


@dataclass(kw_only=True)
class Neo4jGraphProjection:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def apply(self, event: ChangeNotification) -> None:
        """Fetch current source snapshot and update projection/checkpoint idempotently"""
        raise NotImplementedError("Fetch current source snapshot and update projection/checkpoint idempotently")

    async def rebuild(self) -> None:
        """Rebuild from authoritative snapshot with version reconciliation"""
        raise NotImplementedError("Rebuild from authoritative snapshot with version reconciliation")
