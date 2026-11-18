from dataclasses import dataclass
from ingestion_service.application.ports.replay_store import ReplayStore

@dataclass
class ReplayOperations:
    jobs: ReplayStore

    async def start(self, snapshot_id: str, rate: int, key: str):
        self.validate_rate(rate)
        if not key or len(key) > 128:
            raise ValueError('Idempotency-Key must contain 1–128 characters')
        return await self.jobs.create_job(snapshot_id, rate, key)

    @staticmethod
    def validate_rate(rate):
        if not 10 <= rate <= 5000:
            raise ValueError('Rate must be between 10 and 5000 documents/s')

    async def change(self, job_id, action, rate=None):
        if action == 'rate':
            self.validate_rate(rate)
        elif action not in ('pause', 'resume'):
            raise ValueError('Unknown operation')
        return await self.jobs.change_job(job_id, action, rate)
