from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from typing import Protocol


@dataclass(kw_only=True)
class PasswordHashingAdapter:
    """Concrete technology adapter stub; all I/O remains unimplemented."""

    connection_url: str

    async def hash(self, password: str) -> str:
        """Hash password using selected secure algorithm"""
        raise NotImplementedError("Hash password using selected secure algorithm")

    async def verify(self, password: str, password_hash: str) -> bool:
        """Verify password without logging credentials"""
        raise NotImplementedError("Verify password without logging credentials")
