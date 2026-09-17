from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import StoreSourceDocumentBatch, BatchCompleted
from content_service.application.repositories.source_document_repository import SourceDocumentRepository
from content_service.application.ports.unit_of_work import UnitOfWork


@dataclass(kw_only=True)
class SourceDocumentCommandService:
    """Owns the primary raw text corpus."""

    repository: SourceDocumentRepository
    unit_of_work: UnitOfWork

    async def store_batch(self, command: StoreSourceDocumentBatch) -> BatchCompleted:
        """Deduplicate batch; atomically persist sharded corpus and outbox"""
        raise NotImplementedError("Deduplicate batch; atomically persist sharded corpus and outbox")
