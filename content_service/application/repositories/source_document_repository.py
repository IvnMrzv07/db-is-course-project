from __future__ import annotations

from content_service.domain.entities.source_document import SourceDocument
from .crud_repository import CrudRepository
from typing import Protocol


class SourceDocumentRepository(CrudRepository[SourceDocument], Protocol):
    """CRUD port for locally owned SourceDocument records."""
