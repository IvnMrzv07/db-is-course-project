from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.interview_dto import InterviewDTO
from content_service.application.repositories.interview_repository import InterviewRepository


class InterviewQueryService:
    """Read use cases; enforce visibility before returning a DTO."""

    def __init__(self, repository: InterviewRepository) -> None:
        self.repository = repository

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> InterviewDTO | None:
        raise NotImplementedError("Visibility-aware read and DTO mapping")

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[InterviewDTO, ...]:
        raise NotImplementedError("Filtered bounded query")
