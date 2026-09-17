from __future__ import annotations

from content_service.domain.entities.interview import Interview
from content_service.application.dtos.interview_dto import InterviewDTO


class InterviewDTOMapper:
    """Maps domain values into the application response representation."""

    @staticmethod
    def to_dto(entity: Interview) -> InterviewDTO:
        raise NotImplementedError("Explicit field mapping")
