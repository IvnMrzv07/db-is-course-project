from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import ChangeNotification


class GraphProjection(Protocol):
    """Outbound port owned by this application."""

    async def apply(self, event: ChangeNotification) -> None:
        """Fetch current source snapshot and update projection/checkpoint idempotently"""
        ...

    async def rebuild(self) -> None:
        """Rebuild from authoritative snapshot with version reconciliation"""
        ...
