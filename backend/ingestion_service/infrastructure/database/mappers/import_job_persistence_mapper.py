from __future__ import annotations

from ingestion_service.domain.entities.import_job import ImportJob
from ingestion_service.infrastructure.database.models.import_job_model import ImportJobModel


class ImportJobPersistenceMapper:
    @staticmethod
    def to_domain(model: ImportJobModel) -> ImportJob:
        raise NotImplementedError("Complete persisted field mapping")

    @staticmethod
    def to_model(entity: ImportJob) -> ImportJobModel:
        raise NotImplementedError("Complete persisted field mapping")
