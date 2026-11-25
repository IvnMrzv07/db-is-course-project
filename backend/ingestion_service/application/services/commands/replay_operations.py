from dataclasses import dataclass
from ingestion_service.application.ports.replay_store import ReplayStore

MAX_RATE = 0  # no pacing: as fast as the pipeline accepts
RATE_LIMITS = (10, 100_000)


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
        if rate != MAX_RATE and not RATE_LIMITS[0] <= rate <= RATE_LIMITS[1]:
            raise ValueError('Rate must be 0 (unlimited) or between 10 and 100000 documents/s')

    async def change(self, job_id, action, rate=None):
        if action == 'cancel':
            return await self.jobs.cancel_job(job_id)
        if action == 'rate':
            self.validate_rate(rate)
        elif action not in ('pause', 'resume'):
            raise ValueError('Unknown operation')
        return await self.jobs.change_job(job_id, action, rate)
