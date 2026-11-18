from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class Interview:
    """Domain record; validation rules are specified but not implemented."""

    id: UUID
    version: int
    player_id: UUID
    title: str
    questions_and_answers: tuple[tuple[str, str], ...]
    source_url: str
    publication_status: str
