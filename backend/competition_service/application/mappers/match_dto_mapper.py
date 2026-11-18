from __future__ import annotations

from competition_service.domain.entities.match import Match
from competition_service.application.dtos.match_dto import MatchDTO


class MatchDTOMapper:
    """Maps domain values into the application response representation."""

    @staticmethod
    def to_dto(entity: Match) -> MatchDTO:
        raise NotImplementedError("Explicit field mapping")
