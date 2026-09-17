from __future__ import annotations

from dataclasses import dataclass
from ingestion_service.settings import Settings
from ingestion_service.infrastructure.database.unit_of_work_adapter import PostgresUnitOfWork
from ingestion_service.infrastructure.database.repositories.postgres_import_job_repository import PostgresImportJobRepository
from ingestion_service.infrastructure.database.repositories.postgres_replay_job_repository import PostgresReplayJobRepository
from ingestion_service.infrastructure.database.repositories.postgres_enrichment_job_repository import PostgresEnrichmentJobRepository
from ingestion_service.infrastructure.database.repositories.postgres_validation_issue_repository import PostgresValidationIssueRepository
from ingestion_service.infrastructure.database.repositories.postgres_identity_candidate_repository import PostgresIdentityCandidateRepository
from ingestion_service.infrastructure.datasets.dataset_reader_adapter import KaggleAndTextFileReader
from ingestion_service.infrastructure.messaging.command_publisher_adapter import RabbitMQCommandPublisher
from ingestion_service.infrastructure.pacing.rate_controller_adapter import AsyncioRateController
from ingestion_service.infrastructure.providers.pandascore_adapter import PandaScoreAdapter
from ingestion_service.application.services.commands.import_service import ImportService
from ingestion_service.presentation.api.controllers.import_service_controller import ImportServiceController
from ingestion_service.application.services.queries.import_query_service import ImportQueryService
from ingestion_service.presentation.api.controllers.import_query_service_controller import ImportQueryServiceController
from ingestion_service.application.services.commands.replay_command_service import ReplayCommandService
from ingestion_service.presentation.api.controllers.replay_command_service_controller import ReplayCommandServiceController
from ingestion_service.application.services.queries.replay_query_service import ReplayQueryService
from ingestion_service.presentation.api.controllers.replay_query_service_controller import ReplayQueryServiceController
from ingestion_service.application.services.commands.enrichment_service import EnrichmentService
from ingestion_service.presentation.api.controllers.enrichment_service_controller import EnrichmentServiceController
from ingestion_service.application.services.commands.import_review_service import ImportReviewService
from ingestion_service.presentation.api.controllers.import_review_service_controller import ImportReviewServiceController
from ingestion_service.application.services.commands.batch_completion_service import BatchCompletionService
from ingestion_service.presentation.messaging.consumers.batch_completed_consumer import BatchCompletedConsumer


@dataclass(kw_only=True)
class Container:
    """Inspectable object graph; not a running application."""

    import_service_controller: ImportServiceController
    import_query_service_controller: ImportQueryServiceController
    replay_command_service_controller: ReplayCommandServiceController
    replay_query_service_controller: ReplayQueryServiceController
    enrichment_service_controller: EnrichmentServiceController
    import_review_service_controller: ImportReviewServiceController
    batch_consumer: BatchCompletedConsumer


def build_container(settings: Settings) -> Container:
    """Wire stub adapters without connecting to any external system.

    Create request/job-scoped units of work when implementing runtime lifecycles.
    Empty connection strings are placeholders here, not valid deployment defaults.
    """
    uow = PostgresUnitOfWork(connection_url=settings.database_url or "")
    import_job_repo = PostgresImportJobRepository(connection_url=settings.database_url or "")
    replay_job_repo = PostgresReplayJobRepository(connection_url=settings.database_url or "")
    enrichment_job_repo = PostgresEnrichmentJobRepository(connection_url=settings.database_url or "")
    validation_issue_repo = PostgresValidationIssueRepository(connection_url=settings.database_url or "")
    identity_candidate_repo = PostgresIdentityCandidateRepository(connection_url=settings.database_url or "")
    reader = KaggleAndTextFileReader(connection_url=settings.database_url or "")
    publisher = RabbitMQCommandPublisher(connection_url=settings.broker_url or "")
    pacer = AsyncioRateController(connection_url=settings.database_url or "")
    provider = PandaScoreAdapter(base_url=settings.provider_base_url, api_key=settings.provider_api_key)
    import_service = ImportService(jobs=import_job_repo, reader=reader, publisher=publisher, unit_of_work=uow)
    import_service_controller = ImportServiceController(service=import_service)
    import_query_service = ImportQueryService(jobs=import_job_repo)
    import_query_service_controller = ImportQueryServiceController(service=import_query_service)
    replay_command_service = ReplayCommandService(jobs=replay_job_repo, pacer=pacer, reader=reader, publisher=publisher, unit_of_work=uow)
    replay_command_service_controller = ReplayCommandServiceController(service=replay_command_service)
    replay_query_service = ReplayQueryService(jobs=replay_job_repo)
    replay_query_service_controller = ReplayQueryServiceController(service=replay_query_service)
    enrichment_service = EnrichmentService(provider=provider, jobs=enrichment_job_repo, candidates=identity_candidate_repo, unit_of_work=uow)
    enrichment_service_controller = EnrichmentServiceController(service=enrichment_service)
    import_review_service = ImportReviewService(candidates=identity_candidate_repo, unit_of_work=uow)
    import_review_service_controller = ImportReviewServiceController(service=import_review_service)
    completions = BatchCompletionService(imports=import_job_repo, replays=replay_job_repo, unit_of_work=uow)
    batch_consumer = BatchCompletedConsumer(service=completions)
    return Container(
        import_service_controller=import_service_controller,
        import_query_service_controller=import_query_service_controller,
        replay_command_service_controller=replay_command_service_controller,
        replay_query_service_controller=replay_query_service_controller,
        enrichment_service_controller=enrichment_service_controller,
        import_review_service_controller=import_review_service_controller,
        batch_consumer=batch_consumer,
    )
