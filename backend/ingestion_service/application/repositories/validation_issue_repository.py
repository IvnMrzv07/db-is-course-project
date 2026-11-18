from __future__ import annotations

from ingestion_service.domain.entities.validation_issue import ValidationIssue
from .crud_repository import CrudRepository
from typing import Protocol


class ValidationIssueRepository(CrudRepository[ValidationIssue], Protocol):
    """CRUD port for locally owned ValidationIssue records."""
