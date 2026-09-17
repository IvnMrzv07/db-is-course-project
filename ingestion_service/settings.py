from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Settings:
    """Deployment configuration; never commit real credentials."""

    service_name: str
    database_url: str | None = None
    broker_url: str | None = None
    cache_url: str | None = None
    log_level: str = "INFO"
    graph_url: str | None = None
    search_url: str | None = None
    provider_base_url: str = ""
    provider_api_key: str = ""
