from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from ingestion_service.application.dtos.provider_metadata_dto import ProviderMetadataDTO


@dataclass(kw_only=True)
class LiquipediaAdapter:
    """External source adapter stub; access must be configured and verified."""

    base_url: str
    api_key: str

    async def fetch(self, entity_type: str, external_ids: tuple[str, ...]) -> tuple[ProviderMetadataDTO, ...]:
        """Retrieve source metadata within approved access and rate limits"""
        raise NotImplementedError("Retrieve source metadata within approved access and rate limits")
