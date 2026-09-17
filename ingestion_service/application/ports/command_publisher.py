from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import ImportMatchBatch, StoreSourceDocumentBatch


class CommandPublisher(Protocol):
    """Outbound port owned by this application."""

    async def publish_match_batch(self, command: ImportMatchBatch) -> None:
        """Publish committed outbox command with confirm"""
        ...

    async def publish_document_batch(self, command: StoreSourceDocumentBatch) -> None:
        """Publish committed document command with confirm"""
        ...
