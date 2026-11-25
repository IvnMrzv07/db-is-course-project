from dataclasses import dataclass
from content_service.application.services.queries.cluster_status_query_service import ClusterStatusQueryService


@dataclass
class ClusterStatusController:
    queries: ClusterStatusQueryService

    async def status(self) -> dict:
        return await self.queries.status()
