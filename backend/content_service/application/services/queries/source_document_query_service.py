from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID
from content_service.application.dtos.source_document_snapshot_dto import SourceDocumentSnapshotDTO
from content_service.application.repositories.source_document_repository import SourceDocumentRepository


@dataclass(kw_only=True)
class SourceDocumentQueryService:
    repository: SourceDocumentRepository

    async def get_snapshot(self, document_id: UUID, *, service_identity: str) -> SourceDocumentSnapshotDTO | None:
        """Authorize owner read; return eligible fields or a retained versioned tombstone."""
        raise NotImplementedError("Read current publication state without exposing draft text")
