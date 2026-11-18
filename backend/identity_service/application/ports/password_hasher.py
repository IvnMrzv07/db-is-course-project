from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol


class PasswordHasher(Protocol):
    """Outbound port owned by this application."""

    async def hash(self, password: str) -> str:
        """Hash password using selected secure algorithm"""
        ...

    async def verify(self, password: str, password_hash: str) -> bool:
        """Verify password without logging credentials"""
        ...
