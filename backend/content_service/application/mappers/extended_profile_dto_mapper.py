from __future__ import annotations

from content_service.domain.entities.extended_profile import ExtendedProfile
from content_service.application.dtos.extended_profile_dto import ExtendedProfileDTO


class ExtendedProfileDTOMapper:
    """Maps domain values into the application response representation."""

    @staticmethod
    def to_dto(entity: ExtendedProfile) -> ExtendedProfileDTO:
        raise NotImplementedError("Explicit field mapping")
