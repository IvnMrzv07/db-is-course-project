import os
from pymongo import AsyncMongoClient
from content_service.infrastructure.database.corpus_repository import MongoCorpusRepository
from content_service.application.services.queries.corpus_query_service import CorpusQueryService
from content_service.application.services.commands.corpus_command_service import CorpusCommandService
from content_service.presentation.api.controllers.corpus_controller import CorpusController
from content_service.infrastructure.database.distributed_aggregation import MongoDistributedAggregation
from content_service.application.services.queries.distributed_aggregation_query_service import DistributedAggregationQueryService
from content_service.presentation.api.controllers.distributed_aggregation_controller import DistributedAggregationController

async def build_runtime():
    client = AsyncMongoClient(os.environ['MONGO_URL'], serverSelectionTimeoutMS=5000, tz_aware=True)
    repository = MongoCorpusRepository(client.get_database('content'))
    await repository.initialize()
    return client, repository, CorpusController(CorpusQueryService(repository)), CorpusCommandService(repository)


def build_distributed_controller(client) -> DistributedAggregationController:
    """Read-only map-reduce slice; shares the API's Mongo client (mongos on the cs-sharded stack)."""
    reader = MongoDistributedAggregation(client.get_database('content'))
    return DistributedAggregationController(DistributedAggregationQueryService(reader))
