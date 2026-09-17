from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class HighlightDTO:
    """Application response; no driver or HTTP types."""

    id: UUID
    version: int
    match_id: UUID
    title: str
    video_url: str
    source_url: str
    publication_status: str
