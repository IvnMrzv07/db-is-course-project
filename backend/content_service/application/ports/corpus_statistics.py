from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from content_service.application.dtos.corpus_statistics_dto import CorpusStatisticsDTO


class CorpusStatisticsReader(Protocol):
    """Outbound port owned by this application."""

    async def sample(self, corpus_scope: str) -> CorpusStatisticsDTO:
        """Read committed database-backed counts, not broker counters"""
        ...
