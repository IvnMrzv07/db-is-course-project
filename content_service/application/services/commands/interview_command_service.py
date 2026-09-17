from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.interview_commands import CreateInterview, UpdateInterview
from content_service.application.dtos.interview_dto import InterviewDTO
from content_service.application.repositories.interview_repository import InterviewRepository
from content_service.application.ports.unit_of_work import UnitOfWork


class InterviewCommandService:
    """Authorize actor, validate domain state, and atomically persist changes/outbox."""

    def __init__(self, repository: InterviewRepository, unit_of_work: UnitOfWork) -> None:
        self.repository = repository
        self.unit_of_work = unit_of_work

    async def create(self, command: CreateInterview) -> InterviewDTO:
        raise NotImplementedError("Authorize, validate, create, stage event, commit")

    async def update(self, command: UpdateInterview) -> InterviewDTO:
        raise NotImplementedError("Authorize, validate version and replacement, commit")

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        raise NotImplementedError("Authorize and apply versioned removal policy")
