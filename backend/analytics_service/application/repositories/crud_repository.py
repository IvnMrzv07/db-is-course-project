from __future__ import annotations


from typing import Protocol, TypeVar
from uuid import UUID

T = TypeVar('T')

class CrudRepository(Protocol[T]):
    """Local persistence port, not an authorization boundary or an HTTP API.

    Mutations participate in a unit of work; they do not commit independently.
    Implementations reject missing/stale updates and duplicate creates.
    """

    async def create(self, entity: T) -> T: ...
    async def get(self, entity_id: UUID) -> T | None: ...
    async def list(self, *, limit: int = 50, offset: int = 0) -> tuple[T, ...]: ...
    async def update(self, entity: T, *, expected_version: int) -> T: ...
    async def delete(self, entity_id: UUID, *, expected_version: int) -> None: ...
