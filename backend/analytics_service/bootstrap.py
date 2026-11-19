from __future__ import annotations

from dataclasses import dataclass
from analytics_service.settings import Settings
from analytics_service.infrastructure.database.unit_of_work_adapter import PostgresUnitOfWork
from analytics_service.infrastructure.database.statistics_reader_adapter import PostgresStatisticsReader
from analytics_service.infrastructure.cache.comparison_cache_adapter import RedisComparisonCache
from analytics_service.infrastructure.database.relationship_reader_adapter import PostgresRelationshipReader
from analytics_service.infrastructure.database.statistics_projection_adapter import PostgresStatisticsProjection
from analytics_service.application.services.queries.comparison_service import ComparisonService
from analytics_service.presentation.api.controllers.comparison_service_controller import ComparisonServiceController
from analytics_service.application.services.queries.relationship_service import RelationshipService
from analytics_service.presentation.api.controllers.relationship_service_controller import RelationshipServiceController
from analytics_service.application.services.queries.recommendation_service import RecommendationService
from analytics_service.presentation.api.controllers.recommendation_service_controller import RecommendationServiceController
from analytics_service.application.services.commands.statistics_projection_service import StatisticsProjectionService
from analytics_service.presentation.messaging.consumers.statistics_event_consumer import StatisticsEventConsumer


@dataclass(kw_only=True)
class Container:
    """Inspectable object graph; not a running application."""

    comparison_service_controller: ComparisonServiceController
    relationship_service_controller: RelationshipServiceController
    recommendation_service_controller: RecommendationServiceController
    statistics_consumer: StatisticsEventConsumer


def build_container(settings: Settings) -> Container:
    """Wire stub adapters without connecting to any external system.

    Create request/job-scoped units of work when implementing runtime lifecycles.
    Empty connection strings are placeholders here, not valid deployment defaults.
    """
    uow = PostgresUnitOfWork(connection_url=settings.database_url or "")
    statistics = PostgresStatisticsReader(connection_url=settings.database_url or "")
    cache = RedisComparisonCache(connection_url=settings.cache_url or "")
    relationships = PostgresRelationshipReader(connection_url=settings.database_url or "")
    statistics_projection = PostgresStatisticsProjection(connection_url=settings.database_url or "")
    comparison_service = ComparisonService(reader=statistics, cache=cache)
    comparison_service_controller = ComparisonServiceController(service=comparison_service)
    relationship_service = RelationshipService(reader=relationships)
    relationship_service_controller = RelationshipServiceController(service=relationship_service)
    recommendation_service = RecommendationService(reader=statistics)
    recommendation_service_controller = RecommendationServiceController(service=recommendation_service)
    statistics_commands = StatisticsProjectionService(projection=statistics_projection)
    statistics_consumer = StatisticsEventConsumer(service=statistics_commands)
    return Container(
        comparison_service_controller=comparison_service_controller,
        relationship_service_controller=relationship_service_controller,
        recommendation_service_controller=recommendation_service_controller,
        statistics_consumer=statistics_consumer,
    )
