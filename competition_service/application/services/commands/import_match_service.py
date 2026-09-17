from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import ImportMatchBatch, BatchCompleted
from competition_service.application.repositories.match_repository import MatchRepository
from competition_service.application.ports.unit_of_work import UnitOfWork


@dataclass(kw_only=True)
class ImportMatchService:
    """Import command handler."""

    repository: MatchRepository
    unit_of_work: UnitOfWork

    async def import_batch(self, command: ImportMatchBatch) -> BatchCompleted:
        """Validate series versus maps and idempotently commit records plus events"""
        raise NotImplementedError("Validate series versus maps and idempotently commit records plus events")
