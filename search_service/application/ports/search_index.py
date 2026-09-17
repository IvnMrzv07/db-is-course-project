from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import ChangeNotification


class SearchIndex(Protocol):
    """Outbound port owned by this application."""

    async def apply(self, event: ChangeNotification) -> None:
        """Fetch eligible current source snapshot; versioned upsert or tombstone"""
        ...

    async def rebuild(self, corpus_scope: str) -> None:
        """Reindex and reconcile concurrent owner changes"""
        ...
