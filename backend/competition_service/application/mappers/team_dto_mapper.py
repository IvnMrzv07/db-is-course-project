from __future__ import annotations

from competition_service.domain.entities.team import Team
from competition_service.application.dtos.team_dto import TeamDTO


class TeamDTOMapper:
    """Maps domain values into the application response representation."""

    @staticmethod
    def to_dto(entity: Team) -> TeamDTO:
        raise NotImplementedError("Explicit field mapping")
