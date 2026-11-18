from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from contracts.messages import ChangeNotification


@dataclass(kw_only=True)
class ElasticsearchIndex:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def apply(self, event: ChangeNotification) -> None:
        """Fetch eligible current source snapshot; versioned upsert or tombstone"""
        raise NotImplementedError("Fetch eligible current source snapshot; versioned upsert or tombstone")

    async def rebuild(self, corpus_scope: str) -> None:
        """Reindex and reconcile concurrent owner changes"""
        raise NotImplementedError("Reindex and reconcile concurrent owner changes")
