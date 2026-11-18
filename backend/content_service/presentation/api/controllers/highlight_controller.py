from __future__ import annotations

from uuid import UUID
from content_service.application.dtos.highlight_commands import CreateHighlight, UpdateHighlight
from content_service.application.dtos.highlight_dto import HighlightDTO
from content_service.application.services.commands.highlight_command_service import HighlightCommandService
from content_service.application.services.queries.highlight_query_service import HighlightQueryService


class HighlightController:
    """HTTP adapter skeleton; trusted actor IDs come from authentication, not request JSON.

    FastAPI route registration, schema conversion, error mapping and auth are pending.
    """

    def __init__(self, commands: HighlightCommandService, queries: HighlightQueryService) -> None:
        self.commands = commands
        self.queries = queries

    async def create(self, command: CreateHighlight) -> HighlightDTO:
        return await self.commands.create(command)

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> HighlightDTO | None:
        return await self.queries.get(entity_id, viewer_id=viewer_id)

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[HighlightDTO, ...]:
        return await self.queries.list(viewer_id=viewer_id, limit=limit, offset=offset)

    async def update(self, command: UpdateHighlight) -> HighlightDTO:
        return await self.commands.update(command)

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        await self.commands.delete(entity_id, actor_id=actor_id, expected_version=expected_version)
