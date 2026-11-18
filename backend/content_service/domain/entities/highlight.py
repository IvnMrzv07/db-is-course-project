from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Highlight:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    match_id: UUID
    title: str
    video_url: str
    source_url: str
    publication_status: str
