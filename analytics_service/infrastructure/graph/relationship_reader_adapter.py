from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from analytics_service.application.dtos.relationship_dto import RelationshipDTO


@dataclass(kw_only=True)
class Neo4jRelationshipReader:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def find_connections(self, player_id: UUID, max_depth: int) -> tuple[RelationshipDTO, ...]:
        """Traverse bounded graph with participation evidence"""
        raise NotImplementedError("Traverse bounded graph with participation evidence")
