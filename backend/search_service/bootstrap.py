from __future__ import annotations

from dataclasses import dataclass
from search_service.settings import Settings
from search_service.infrastructure.database.unit_of_work_adapter import PostgresUnitOfWork
from search_service.infrastructure.search.search_reader_adapter import ElasticsearchReader
from search_service.infrastructure.cache.search_cache_adapter import RedisSearchCache
from search_service.infrastructure.search.search_history_adapter import ElasticsearchHistory
from search_service.infrastructure.search.search_index_adapter import ElasticsearchIndex
from search_service.application.services.queries.search_service import SearchService
from search_service.presentation.api.controllers.search_service_controller import SearchServiceController
from search_service.application.services.queries.search_statistics_query_service import SearchStatisticsQueryService
from search_service.presentation.api.controllers.search_statistics_query_service_controller import SearchStatisticsQueryServiceController
from search_service.application.services.commands.indexing_service import IndexingService
from search_service.presentation.messaging.consumers.indexing_event_consumer import IndexingEventConsumer


@dataclass(kw_only=True)
class Container:
    """Inspectable object graph; not a running application."""

    search_service_controller: SearchServiceController
    search_statistics_query_service_controller: SearchStatisticsQueryServiceController
    index_consumer: IndexingEventConsumer


def build_container(settings: Settings) -> Container:
    """Wire stub adapters without connecting to any external system.

    Create request/job-scoped units of work when implementing runtime lifecycles.
    Empty connection strings are placeholders here, not valid deployment defaults.
    """
    uow = PostgresUnitOfWork(connection_url=settings.database_url or "")
    reader = ElasticsearchReader(connection_url=settings.search_url or "")
    cache = RedisSearchCache(connection_url=settings.cache_url or "")
    history = ElasticsearchHistory(connection_url=settings.search_url or "")
    index = ElasticsearchIndex(connection_url=settings.search_url or "")
    search_service = SearchService(reader=reader, cache=cache, history=history)
    search_service_controller = SearchServiceController(service=search_service)
    search_statistics_query_service = SearchStatisticsQueryService(history=history)
    search_statistics_query_service_controller = SearchStatisticsQueryServiceController(service=search_statistics_query_service)
    indexing = IndexingService(index=index)
    index_consumer = IndexingEventConsumer(service=indexing)
    return Container(
        search_service_controller=search_service_controller,
        search_statistics_query_service_controller=search_statistics_query_service_controller,
        index_consumer=index_consumer,
    )
