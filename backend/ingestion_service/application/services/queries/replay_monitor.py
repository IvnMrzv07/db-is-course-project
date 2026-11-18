from dataclasses import dataclass
from ingestion_service.application.ports.replay_store import ReplayStore

@dataclass
class ReplayMonitor:
    jobs: ReplayStore

    async def list(self, page=1, page_size=20):
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError('Invalid pagination')
        return await self.jobs.list_jobs(page, page_size)

    async def get(self, job_id):
        return await self.jobs.get_job(job_id)

    async def snapshots(self):
        return await self.jobs.snapshots()
