from __future__ import annotations

from uuid import UUID
from ..entities.match import Match


class MatchResultValidator:
    """Pure domain policy stub; does not perform I/O."""

    def validate(self, match: Match) -> None:
        raise NotImplementedError("Implement domain rules")
