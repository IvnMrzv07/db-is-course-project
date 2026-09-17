from __future__ import annotations

from competition_service.domain.entities.player import Player
from competition_service.infrastructure.database.models.player_model import PlayerModel


class PlayerPersistenceMapper:
    @staticmethod
    def to_domain(model: PlayerModel) -> Player:
        raise NotImplementedError("Complete persisted field mapping")

    @staticmethod
    def to_model(entity: Player) -> PlayerModel:
        raise NotImplementedError("Complete persisted field mapping")
