from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol
from identity_service.application.dtos.account_dto import AccountDTO
from identity_service.application.dtos.registration_dto import RegistrationDTO
from identity_service.application.dtos.login_dto import LoginDTO
from identity_service.application.dtos.credential_dto import CredentialDTO
from identity_service.application.repositories.user_repository import UserRepository
from identity_service.application.ports.password_hasher import PasswordHasher
from identity_service.application.ports.credential_issuer import CredentialIssuer
from identity_service.application.ports.unit_of_work import UnitOfWork
from identity_service.application.services.queries.account_query_service import AccountQueryService


@dataclass(kw_only=True)
class AccountQueryServiceController:
    """HTTP boundary stub: authenticate, map schemas, delegate, and translate errors. No routes registered yet."""

    service: AccountQueryService

    async def get_me(self, actor_id: UUID) -> AccountDTO:
        """Return own safe account DTO without password hash"""
        raise NotImplementedError("Return own safe account DTO without password hash")
