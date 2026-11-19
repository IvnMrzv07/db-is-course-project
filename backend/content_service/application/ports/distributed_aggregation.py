from typing import Protocol
from content_service.application.dtos.distributed_query import DistributedAggregationQuery


class DistributedAggregationReader(Protocol):
    async def count(self, query: DistributedAggregationQuery) -> int:
        """Number of documents matched by the query filter (before grouping)."""
        ...

    async def execute(self, query: DistributedAggregationQuery, engine: str) -> dict:
        """Run one engine ('aggregate' | 'mapreduce').

        Returns {'engine', 'rows', 'elapsed_ms', 'plan'}; rows are flat raw sums ordered by the metric's
        sort order, so both engines are directly comparable.
        """
        ...

    async def topology(self) -> dict:
        """{'sharded': bool, 'shards': [{'shard', 'documents'}]} for content.source_documents."""
        ...
