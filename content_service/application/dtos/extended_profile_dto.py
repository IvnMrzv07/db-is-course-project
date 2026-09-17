from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class ExtendedProfileDTO:
    """Application response; no driver or HTTP types."""

    id: UUID
    version: int
    player_id: UUID
    biography: str
    play_style_tags: tuple[str, ...]
    source_urls: tuple[str, ...]
    publication_status: str
