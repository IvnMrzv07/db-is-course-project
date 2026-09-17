from __future__ import annotations

from uuid import UUID
from competition_service.application.dtos.tournament_commands import CreateTournament, UpdateTournament
from competition_service.application.dtos.tournament_dto import TournamentDTO
from competition_service.application.services.commands.tournament_command_service import TournamentCommandService
from competition_service.application.services.queries.tournament_query_service import TournamentQueryService


class TournamentController:
    """HTTP adapter skeleton; trusted actor IDs come from authentication, not request JSON.

    FastAPI route registration, schema conversion, error mapping and auth are pending.
    """

    def __init__(self, commands: TournamentCommandService, queries: TournamentQueryService) -> None:
        self.commands = commands
        self.queries = queries

    async def create(self, command: CreateTournament) -> TournamentDTO:
        return await self.commands.create(command)

    async def get(self, entity_id: UUID, *, viewer_id: UUID | None = None) -> TournamentDTO | None:
        return await self.queries.get(entity_id, viewer_id=viewer_id)

    async def list(self, *, viewer_id: UUID | None = None, limit: int = 50, offset: int = 0) -> tuple[TournamentDTO, ...]:
        return await self.queries.list(viewer_id=viewer_id, limit=limit, offset=offset)

    async def update(self, command: UpdateTournament) -> TournamentDTO:
        return await self.commands.update(command)

    async def delete(self, entity_id: UUID, *, actor_id: UUID, expected_version: int) -> None:
        await self.commands.delete(entity_id, actor_id=actor_id, expected_version=expected_version)
