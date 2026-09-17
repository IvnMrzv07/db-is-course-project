from __future__ import annotations

from content_service.domain.entities.interview import Interview
from .crud_repository import CrudRepository
from typing import Protocol


class InterviewRepository(CrudRepository[Interview], Protocol):
    """CRUD port for locally owned Interview records."""
