from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.interview_commands import CreateInterview, UpdateInterview
from content_service.application.dtos.interview_dto import InterviewDTO
from content_service.application.services.commands.interview_command_service import InterviewCommandService
from content_service.application.services.queries.interview_query_service import InterviewQueryService


class InterviewController:
    """HTTP adapter skeleton; trusted actor IDs come from authentication, not request JSON.

    FastAPI route registration, schema conversion, error mapping and auth are pending.
    """

    def __init__(self, commands: InterviewCommandService, queries: InterviewQueryService) -> None:
        self.commands = commands
        self.queries = queries

    async def create(self, command: CreateInterview) -> InterviewDTO:
        return await self.commands.create(command)

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> InterviewDTO | None:
        return await self.queries.get(entity_id, viewer_id=viewer_id)

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[InterviewDTO, ...]:
        return await self.queries.list(viewer_id=viewer_id, limit=limit, offset=offset)

    async def update(self, command: UpdateInterview) -> InterviewDTO:
        return await self.commands.update(command)

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        await self.commands.delete(entity_id, actor_id=actor_id, expected_version=expected_version)
