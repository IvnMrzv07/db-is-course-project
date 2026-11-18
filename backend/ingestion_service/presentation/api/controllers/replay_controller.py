from dataclasses import dataclass
from ingestion_service.application.services.commands.replay_operations import ReplayOperations
from ingestion_service.application.services.queries.replay_monitor import ReplayMonitor

@dataclass
class ReplayController:
    commands: ReplayOperations
    queries: ReplayMonitor

    async def start(self, snapshot_id, rate, key):
        return await self.commands.start(snapshot_id, rate, key)

    async def change(self, job_id, action, rate=None):
        return await self.commands.change(job_id, action, rate)

    async def list(self, page, page_size):
        return await self.queries.list(page, page_size)

    async def get(self, job_id):
        return await self.queries.get(job_id)

    async def snapshots(self):
        return await self.queries.snapshots()
