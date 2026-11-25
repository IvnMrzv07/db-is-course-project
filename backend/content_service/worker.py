"""Content background worker: batch consumer and/or outbox dispatcher.

`CONTENT_ROLES` (default `consume,dispatch`) selects the parts to run. Scale `consume` freely; keep a single
`dispatch` process, because every dispatcher publishes all unsent rows (repeats are harmless, but wasteful).
`CONTENT_CONCURRENCY` (default 4) is the number of batch transactions one consumer process runs at once.
"""
import asyncio
import logging
import os
from content_service.runtime import build_runtime, search_index_events_enabled
from content_service.infrastructure.messaging.runtime_broker import Broker
from contracts.messages import SEARCH_INDEX_QUEUE

ROLES = ('consume', 'dispatch')
DISPATCH_BATCH = 50  # index events carry ~1.5 MB each at 500 documents
log = logging.getLogger(__name__)


def worker_roles(value: str | None) -> tuple[str, ...]:
    roles = tuple(part.strip() for part in (value or ','.join(ROLES)).split(',') if part.strip())
    if not roles or any(role not in ROLES for role in roles):
        raise ValueError(f'CONTENT_ROLES must contain only {ROLES}')
    return roles


async def dispatch_once(repository, publish, limit=DISPATCH_BATCH) -> int:
    """Publish unsent rows concurrently; rows without a broker confirm stay unsent for the next cycle."""
    rows = await repository.unsent(limit)
    outcomes = await asyncio.gather(*(publish(row.get('queue', 'corpus.completed'), row['payload']) for row in rows),
                                    return_exceptions=True)
    confirmed = [row for row, outcome in zip(rows, outcomes) if not isinstance(outcome, BaseException)]
    if confirmed:
        await repository.mark_sent(confirmed)
    failures = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
    if failures:
        raise failures[0]
    return len(confirmed)


async def run():
    roles = worker_roles(os.getenv('CONTENT_ROLES'))
    client, repository, controller, commands = await build_runtime()
    queues = Broker.QUEUES + ((SEARCH_INDEX_QUEUE,) if search_index_events_enabled() else ())
    broker = await Broker(queues, concurrency=int(os.getenv('CONTENT_CONCURRENCY', '4'))).connect()

    async def dispatch():
        while True:
            sent = 0
            try:
                sent = await dispatch_once(repository, broker.publish)
            except Exception:
                log.exception('Content outbox dispatch failed; retained for retry')
                await asyncio.sleep(1)
            if sent < DISPATCH_BATCH:
                await asyncio.sleep(.1)

    async def failed(batch, error):
        await broker.publish('corpus.completed', {'job_id': batch['job_id'], 'batch_id': batch['batch_id'], 'error': error})

    tasks = []
    if 'dispatch' in roles:
        tasks.append(asyncio.create_task(dispatch()))
    if 'consume' in roles:
        tasks.append(asyncio.create_task(broker.consume('corpus.store', commands.store, failed)))
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await broker.close()
        await client.close()

if __name__ == '__main__':
    import logging.config, yaml
    with open('deploy/config/runtime-logging.yaml') as source:
        logging.config.dictConfig(yaml.safe_load(source))
    asyncio.run(run())
