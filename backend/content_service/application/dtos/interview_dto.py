from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class InterviewDTO:
    """Application response; no driver or HTTP types."""

    id: UUID
    version: int
    player_id: UUID
    title: str
    questions_and_answers: tuple[tuple[str, str], ...]
    source_url: str
    publication_status: str
