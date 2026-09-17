from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID
from content_service.application.dtos.source_document_snapshot_dto import SourceDocumentSnapshotDTO
from content_service.application.services.queries.source_document_query_service import SourceDocumentQueryService


@dataclass(kw_only=True)
class SourceDocumentController:
    """Internal snapshot API; service identity must come from authenticated transport."""

    queries: SourceDocumentQueryService

    async def get_snapshot(self, document_id: UUID, *, service_identity: str) -> SourceDocumentSnapshotDTO | None:
        return await self.queries.get_snapshot(document_id, service_identity=service_identity)
