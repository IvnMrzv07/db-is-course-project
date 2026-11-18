from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from ingestion_service.application.dtos.provider_metadata_dto import ProviderMetadataDTO


class MetadataProvider(Protocol):
    """Provider-neutral metadata port."""

    async def fetch(self, entity_type: str, external_ids: tuple[str, ...]) -> tuple[ProviderMetadataDTO, ...]:
        """Retrieve source metadata within approved access and rate limits"""
        ...
