from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import ChangeNotification
from search_service.application.ports.search_index import SearchIndex


@dataclass(kw_only=True)
class IndexingService:
    """Index command handler."""

    index: SearchIndex

    async def handle(self, event: ChangeNotification) -> None:
        """Apply committed change without exposing drafts"""
        raise NotImplementedError("Apply committed change without exposing drafts")

    async def rebuild(self, corpus_scope: str) -> None:
        """Rebuild versioned index"""
        raise NotImplementedError("Rebuild versioned index")
