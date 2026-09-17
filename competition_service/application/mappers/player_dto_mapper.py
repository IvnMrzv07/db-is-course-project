from __future__ import annotations

from competition_service.domain.entities.player import Player
from competition_service.application.dtos.player_dto import PlayerDTO


class PlayerDTOMapper:
    """Maps domain values into the application response representation."""

    @staticmethod
    def to_dto(entity: Player) -> PlayerDTO:
        raise NotImplementedError("Explicit field mapping")
