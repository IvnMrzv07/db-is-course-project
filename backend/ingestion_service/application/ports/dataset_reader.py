from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import MatchRecord, SourceDocumentRecord


class DatasetReader(Protocol):
    """Outbound port owned by this application."""

    async def read_matches(self, snapshot_path: str, checkpoint: str | None, limit: int) -> tuple[MatchRecord, ...]:
        """Parse bounded source records and distinguish aggregate rows"""
        ...

    async def read_documents(self, snapshot_path: str, checkpoint: str | None, limit: int) -> tuple[SourceDocumentRecord, ...]:
        """Read prepared real or clearly labeled synthetic corpus"""
        ...
