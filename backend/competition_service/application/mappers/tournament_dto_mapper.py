from __future__ import annotations

from competition_service.domain.entities.tournament import Tournament
from competition_service.application.dtos.tournament_dto import TournamentDTO


class TournamentDTOMapper:
    """Maps domain values into the application response representation."""

    @staticmethod
    def to_dto(entity: Tournament) -> TournamentDTO:
        raise NotImplementedError("Explicit field mapping")
