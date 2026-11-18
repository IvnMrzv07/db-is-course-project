from __future__ import annotations

from content_service.domain.entities.source_document import SourceDocument
from content_service.infrastructure.database.models.source_document_model import SourceDocumentModel


class SourceDocumentPersistenceMapper:
    @staticmethod
    def to_domain(model: SourceDocumentModel) -> SourceDocument:
        raise NotImplementedError("Complete persisted field mapping")

    @staticmethod
    def to_model(entity: SourceDocument) -> SourceDocumentModel:
        raise NotImplementedError("Complete persisted field mapping")
