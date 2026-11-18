from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from analytics_service.application.dtos.relationship_dto import RelationshipDTO
from analytics_service.application.ports.relationship_reader import RelationshipReader


@dataclass(kw_only=True)
class RelationshipService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    reader: RelationshipReader

    async def find_connections(self, player_id: UUID, max_depth: int = 2) -> tuple[RelationshipDTO, ...]:
        """Validate traversal bounds and return evidenced connections"""
        raise NotImplementedError("Validate traversal bounds and return evidenced connections")
