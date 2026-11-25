from dataclasses import dataclass
from content_service.application.ports.cluster_status import ClusterStatus


@dataclass
class ClusterStatusQueryService:
    cluster: ClusterStatus

    async def status(self) -> dict:
        return await self.cluster.status()
