from __future__ import annotations

from dataclasses import dataclass
from content_service.settings import Settings
from content_service.application.services.queries.source_document_query_service import SourceDocumentQueryService
from content_service.presentation.api.controllers.source_document_controller import SourceDocumentController
from content_service.infrastructure.database.unit_of_work_adapter import MongoUnitOfWork
from content_service.infrastructure.database.repositories.mongo_extended_profile_repository import MongoExtendedProfileRepository
from content_service.application.services.commands.extended_profile_command_service import ExtendedProfileCommandService
from content_service.application.services.queries.extended_profile_query_service import ExtendedProfileQueryService
from content_service.presentation.api.controllers.extended_profile_controller import ExtendedProfileController
from content_service.infrastructure.database.repositories.mongo_article_repository import MongoArticleRepository
from content_service.application.services.commands.article_command_service import ArticleCommandService
from content_service.application.services.queries.article_query_service import ArticleQueryService
from content_service.presentation.api.controllers.article_controller import ArticleController
from content_service.infrastructure.database.repositories.mongo_interview_repository import MongoInterviewRepository
from content_service.application.services.commands.interview_command_service import InterviewCommandService
from content_service.application.services.queries.interview_query_service import InterviewQueryService
from content_service.presentation.api.controllers.interview_controller import InterviewController
from content_service.infrastructure.database.repositories.mongo_highlight_repository import MongoHighlightRepository
from content_service.application.services.commands.highlight_command_service import HighlightCommandService
from content_service.application.services.queries.highlight_query_service import HighlightQueryService
from content_service.presentation.api.controllers.highlight_controller import HighlightController
from content_service.infrastructure.database.repositories.mongo_source_document_repository import MongoSourceDocumentRepository
from content_service.infrastructure.database.corpus_statistics_adapter import MongoCorpusStatisticsReader
from content_service.application.services.queries.corpus_statistics_query_service import CorpusStatisticsQueryService
from content_service.presentation.api.controllers.corpus_statistics_query_service_controller import CorpusStatisticsQueryServiceController
from content_service.application.services.commands.source_document_command_service import SourceDocumentCommandService
from content_service.presentation.messaging.consumers.source_document_batch_consumer import SourceDocumentBatchConsumer


@dataclass(kw_only=True)
class Container:
    """Inspectable object graph; not a running application."""

    source_document_controller: SourceDocumentController

    extended_profile_controller: ExtendedProfileController
    article_controller: ArticleController
    interview_controller: InterviewController
    highlight_controller: HighlightController
    corpus_statistics_query_service_controller: CorpusStatisticsQueryServiceController
    document_consumer: SourceDocumentBatchConsumer


def build_container(settings: Settings) -> Container:
    """Wire stub adapters without connecting to any external system.

    Create request/job-scoped units of work when implementing runtime lifecycles.
    Empty connection strings are placeholders here, not valid deployment defaults.
    """
    uow = MongoUnitOfWork(connection_url=settings.database_url or "")
    extended_profile_repo = MongoExtendedProfileRepository(connection_url=settings.database_url or "")
    extended_profile_commands = ExtendedProfileCommandService(repository=extended_profile_repo, unit_of_work=uow)
    extended_profile_queries = ExtendedProfileQueryService(repository=extended_profile_repo)
    extended_profile_controller = ExtendedProfileController(commands=extended_profile_commands, queries=extended_profile_queries)
    article_repo = MongoArticleRepository(connection_url=settings.database_url or "")
    article_commands = ArticleCommandService(repository=article_repo, unit_of_work=uow)
    article_queries = ArticleQueryService(repository=article_repo)
    article_controller = ArticleController(commands=article_commands, queries=article_queries)
    interview_repo = MongoInterviewRepository(connection_url=settings.database_url or "")
    interview_commands = InterviewCommandService(repository=interview_repo, unit_of_work=uow)
    interview_queries = InterviewQueryService(repository=interview_repo)
    interview_controller = InterviewController(commands=interview_commands, queries=interview_queries)
    highlight_repo = MongoHighlightRepository(connection_url=settings.database_url or "")
    highlight_commands = HighlightCommandService(repository=highlight_repo, unit_of_work=uow)
    highlight_queries = HighlightQueryService(repository=highlight_repo)
    highlight_controller = HighlightController(commands=highlight_commands, queries=highlight_queries)
    source_document_repo = MongoSourceDocumentRepository(connection_url=settings.database_url or "")
    corpus_reader = MongoCorpusStatisticsReader(connection_url=settings.database_url or "")
    corpus_statistics_query_service = CorpusStatisticsQueryService(reader=corpus_reader)
    corpus_statistics_query_service_controller = CorpusStatisticsQueryServiceController(service=corpus_statistics_query_service)
    source_documents = SourceDocumentCommandService(repository=source_document_repo, unit_of_work=uow)
    document_consumer = SourceDocumentBatchConsumer(service=source_documents)
    source_document_controller = SourceDocumentController(queries=SourceDocumentQueryService(repository=source_document_repo))
    return Container(
        source_document_controller=source_document_controller,
        extended_profile_controller=extended_profile_controller,
        article_controller=article_controller,
        interview_controller=interview_controller,
        highlight_controller=highlight_controller,
        corpus_statistics_query_service_controller=corpus_statistics_query_service_controller,
        document_consumer=document_consumer,
    )
