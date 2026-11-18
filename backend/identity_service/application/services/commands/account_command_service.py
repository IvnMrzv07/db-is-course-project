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


@dataclass(kw_only=True)
class AccountCommandService:
    """Application use cases. Enforce authorization, validation, and local consistency before I/O."""

    users: UserRepository
    hasher: PasswordHasher
    credentials: CredentialIssuer
    unit_of_work: UnitOfWork

    async def register(self, command: RegistrationDTO) -> AccountDTO:
        """Validate unique identity and hash password before storing user"""
        raise NotImplementedError("Validate unique identity and hash password before storing user")

    async def login(self, command: LoginDTO) -> CredentialDTO:
        """Verify credentials and issue session/token without logging secrets"""
        raise NotImplementedError("Verify credentials and issue session/token without logging secrets")

    async def deactivate(self, user_id: UUID, actor_id: UUID, expected_version: int) -> None:
        """Authorize account deactivation and invalidate credentials"""
        raise NotImplementedError("Authorize account deactivation and invalidate credentials")
