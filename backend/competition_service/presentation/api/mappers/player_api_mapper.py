from __future__ import annotations

from uuid import UUID
from competition_service.presentation.api.schemas.player_request import PlayerRequest
from competition_service.application.dtos.player_commands import CreatePlayer


class PlayerAPIMapper:
    @staticmethod
    def to_command(request: PlayerRequest, *, actor_id: UUID, idempotency_key: str) -> CreatePlayer:
        return CreatePlayer(nickname=request.nickname, real_name=request.real_name,
                            country_code=request.country_code, role=request.role,
                            actor_id=actor_id, idempotency_key=idempotency_key)
