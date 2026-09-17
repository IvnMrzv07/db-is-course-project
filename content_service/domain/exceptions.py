class DomainError(ValueError):
    """Base error for invalid domain state."""


class VersionConflict(DomainError):
    """An optimistic concurrency check failed."""
