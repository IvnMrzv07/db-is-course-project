from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.extended_profile_dto import ExtendedProfileDTO
from content_service.application.repositories.extended_profile_repository import ExtendedProfileRepository


class ExtendedProfileQueryService:
    """Read use cases; enforce visibility before returning a DTO."""

    def __init__(self, repository: ExtendedProfileRepository) -> None:
        self.repository = repository

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> ExtendedProfileDTO | None:
        raise NotImplementedError("Visibility-aware read and DTO mapping")

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[ExtendedProfileDTO, ...]:
        raise NotImplementedError("Filtered bounded query")
