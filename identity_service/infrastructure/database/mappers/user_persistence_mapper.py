from __future__ import annotations

from identity_service.domain.entities.user import User
from identity_service.infrastructure.database.models.user_model import UserModel


class UserPersistenceMapper:
    @staticmethod
    def to_domain(model: UserModel) -> User:
        raise NotImplementedError("Complete persisted field mapping")

    @staticmethod
    def to_model(entity: User) -> UserModel:
        raise NotImplementedError("Complete persisted field mapping")
