from __future__ import annotations

from uuid import UUID
from ..entities.identity_candidate import IdentityCandidate


class EntityResolver:
    """Pure domain policy stub; does not perform I/O."""

    def validate(self, candidate: IdentityCandidate) -> None:
        raise NotImplementedError("Implement domain rules")
