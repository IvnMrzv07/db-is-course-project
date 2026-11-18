from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import ImportMatchBatch, StoreSourceDocumentBatch


@dataclass(kw_only=True)
class RabbitMQCommandPublisher:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def publish_match_batch(self, command: ImportMatchBatch) -> None:
        """Publish committed outbox command with confirm"""
        raise NotImplementedError("Publish committed outbox command with confirm")

    async def publish_document_batch(self, command: StoreSourceDocumentBatch) -> None:
        """Publish committed document command with confirm"""
        raise NotImplementedError("Publish committed document command with confirm")
