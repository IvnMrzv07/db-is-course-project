from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from analytics_service.application.dtos.relationship_dto import RelationshipDTO
from analytics_service.application.ports.relationship_reader import RelationshipReader
from analytics_service.application.services.queries.relationship_service import RelationshipService


@dataclass(kw_only=True)
class RelationshipServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: RelationshipService

    async def find_connections(self, player_id: UUID, max_depth: int = 2) -> tuple[RelationshipDTO, ...]:
        """Validate traversal bounds and return evidenced connections"""
        raise NotImplementedError("Validate traversal bounds and return evidenced connections")
