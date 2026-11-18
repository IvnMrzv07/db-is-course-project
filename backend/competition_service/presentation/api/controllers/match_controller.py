from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.match_commands import CreateMatch, UpdateMatch
from competition_service.application.dtos.match_dto import MatchDTO
from competition_service.application.services.commands.match_command_service import MatchCommandService
from competition_service.application.services.queries.match_query_service import MatchQueryService


class MatchController:
    """HTTP adapter skeleton; trusted actor IDs come from authentication, not request JSON.

    FastAPI route registration, schema conversion, error mapping and auth are pending.
    """

    def __init__(self, commands: MatchCommandService, queries: MatchQueryService) -> None:
        self.commands = commands
        self.queries = queries

    async def create(self, command: CreateMatch) -> MatchDTO:
        return await self.commands.create(command)

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> MatchDTO | None:
        return await self.queries.get(entity_id, viewer_id=viewer_id)

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[MatchDTO, ...]:
        return await self.queries.list(viewer_id=viewer_id, limit=limit, offset=offset)

    async def update(self, command: UpdateMatch) -> MatchDTO:
        return await self.commands.update(command)

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        await self.commands.delete(entity_id, actor_id=actor_id, expected_version=expected_version)
