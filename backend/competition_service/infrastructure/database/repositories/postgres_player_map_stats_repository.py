from __future__ import annotations

from uuid import UUID
from competition_service.domain.entities.player_map_stats import PlayerMapStats
from competition_service.application.repositories.player_map_stats_repository import PlayerMapStatsRepository


class PostgresPlayerMapStatsRepository(PlayerMapStatsRepository):
    """Postgres adapter stub. Never treats a stub call as a successful write."""

    def __init__(self, connection_url: str) -> None:
        self.connection_url = connection_url

    async def create(self, entity: PlayerMapStats) -> PlayerMapStats:
        raise NotImplementedError("Transactional create and serialization")

    async def get(self, entity_id: UUID) -> PlayerMapStats | None:
        raise NotImplementedError("Read by internal ID")

    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[PlayerMapStats, ...]:
        raise NotImplementedError("Bounded query")

    async def update(self, entity: PlayerMapStats, *, expected_version: int) -> PlayerMapStats:
        raise NotImplementedError("Optimistic version check and update")

    async def delete(self, entity_id: UUID, *, expected_version: int) -> None:
        raise NotImplementedError("Versioned removal and referential policy")
