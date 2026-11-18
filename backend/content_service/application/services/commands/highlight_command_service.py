from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.highlight_commands import CreateHighlight, UpdateHighlight
from content_service.application.dtos.highlight_dto import HighlightDTO
from content_service.application.repositories.highlight_repository import HighlightRepository
from content_service.application.ports.unit_of_work import UnitOfWork


class HighlightCommandService:
    """Authorize actor, validate domain state, and atomically persist changes/outbox."""

    def __init__(self, repository: HighlightRepository, unit_of_work: UnitOfWork) -> None:
        self.repository = repository
        self.unit_of_work = unit_of_work

    async def create(self, command: CreateHighlight) -> HighlightDTO:
        raise NotImplementedError("Authorize, validate, create, stage event, commit")

    async def update(self, command: UpdateHighlight) -> HighlightDTO:
        raise NotImplementedError("Authorize, validate version and replacement, commit")

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        raise NotImplementedError("Authorize and apply versioned removal policy")
