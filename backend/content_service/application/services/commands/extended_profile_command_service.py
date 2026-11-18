from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.extended_profile_commands import CreateExtendedProfile, UpdateExtendedProfile
from content_service.application.dtos.extended_profile_dto import ExtendedProfileDTO
from content_service.application.repositories.extended_profile_repository import ExtendedProfileRepository
from content_service.application.ports.unit_of_work import UnitOfWork


class ExtendedProfileCommandService:
    """Authorize actor, validate domain state, and atomically persist changes/outbox."""

    def __init__(self, repository: ExtendedProfileRepository, unit_of_work: UnitOfWork) -> None:
        self.repository = repository
        self.unit_of_work = unit_of_work

    async def create(self, command: CreateExtendedProfile) -> ExtendedProfileDTO:
        raise NotImplementedError("Authorize, validate, create, stage event, commit")

    async def update(self, command: UpdateExtendedProfile) -> ExtendedProfileDTO:
        raise NotImplementedError("Authorize, validate version and replacement, commit")

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        raise NotImplementedError("Authorize and apply versioned removal policy")
