from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import MatchRecord, SourceDocumentRecord


@dataclass(kw_only=True)
class KaggleAndTextFileReader:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def read_matches(self, snapshot_path: str, checkpoint: str | None, limit: int) -> tuple[MatchRecord, ...]:
        """Parse bounded source records and distinguish aggregate rows"""
        raise NotImplementedError("Parse bounded source records and distinguish aggregate rows")

    async def read_documents(self, snapshot_path: str, checkpoint: str | None, limit: int) -> tuple[SourceDocumentRecord, ...]:
        """Read prepared real or clearly labeled synthetic corpus"""
        raise NotImplementedError("Read prepared real or clearly labeled synthetic corpus")
