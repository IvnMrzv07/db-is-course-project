from __future__ import annotations

from content_service.domain.entities.highlight import Highlight
from content_service.application.dtos.highlight_dto import HighlightDTO


class HighlightDTOMapper:
    """Maps domain values into the application response representation."""

    @staticmethod
    def to_dto(entity: Highlight) -> HighlightDTO:
        raise NotImplementedError("Explicit field mapping")
