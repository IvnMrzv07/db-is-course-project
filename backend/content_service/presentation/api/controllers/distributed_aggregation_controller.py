from dataclasses import dataclass
from content_service.application.dtos.distributed_query import DistributedAggregationQuery
from content_service.application.services.queries.distributed_aggregation_query_service import DistributedAggregationQueryService


@dataclass
class DistributedAggregationController:
    queries: DistributedAggregationQueryService

    async def run(self, query: DistributedAggregationQuery) -> dict:
        return await self.queries.run(query)
