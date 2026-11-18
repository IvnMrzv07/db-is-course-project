from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.team_commands import CreateTeam, UpdateTeam
from competition_service.application.dtos.team_dto import TeamDTO
from competition_service.application.services.commands.team_command_service import TeamCommandService
from competition_service.application.services.queries.team_query_service import TeamQueryService


class TeamController:
    """HTTP adapter skeleton; trusted actor IDs come from authentication, not request JSON.

    FastAPI route registration, schema conversion, error mapping and auth are pending.
    """

    def __init__(self, commands: TeamCommandService, queries: TeamQueryService) -> None:
        self.commands = commands
        self.queries = queries

    async def create(self, command: CreateTeam) -> TeamDTO:
        return await self.commands.create(command)

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> TeamDTO | None:
        return await self.queries.get(entity_id, viewer_id=viewer_id)

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[TeamDTO, ...]:
        return await self.queries.list(viewer_id=viewer_id, limit=limit, offset=offset)

    async def update(self, command: UpdateTeam) -> TeamDTO:
        return await self.commands.update(command)

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        await self.commands.delete(entity_id, actor_id=actor_id, expected_version=expected_version)
