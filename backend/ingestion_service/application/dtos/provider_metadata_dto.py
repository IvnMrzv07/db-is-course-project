from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ProviderMetadataDTO:
    """Typed application boundary data."""

    provider: str
    external_id: str
    entity_type: str
    name: str
    country_code: str | None
    source_url: str | None
    retrieved_at: datetime
    attributes: dict[str, str]
