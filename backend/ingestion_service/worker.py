import asyncio
import logging
from ingestion_service.runtime import build_runtime
from ingestion_service.infrastructure.messaging.runtime_broker import Broker

async def run():
    pool, store, controller = await build_runtime()
    broker = await Broker().connect()
    async def produce():
        while True:
            produced = False
            try:
                produced = await store.produce()
            except Exception:
                logging.exception('Producer failed; checkpoint retained')
            await asyncio.sleep(0 if produced else .01)
    async def dispatch():
        while True:
            published = 0
            try:
                published = await store.dispatch(broker.publish)
            except Exception:
                logging.exception('Ingestion outbox dispatch failed; retained for retry')
            await asyncio.sleep(0 if published else .05)
    async def maintain_partitions():
        # Creates upcoming day partitions and drops expired ones (retention); see partitioning.py.
        while True:
            try:
                await store.maintain_partitions()
            except Exception:
                logging.exception('Partition maintenance failed; retried next cycle')
            await asyncio.sleep(store.partition_policy.interval_seconds)
    tasks = [asyncio.create_task(produce()),asyncio.create_task(dispatch()),asyncio.create_task(maintain_partitions()),
             asyncio.create_task(broker.consume('corpus.completed',store.complete))]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await broker.close()
        await pool.close()

if __name__ == '__main__':
    import logging.config, yaml
    with open('deploy/config/runtime-logging.yaml') as source:
        logging.config.dictConfig(yaml.safe_load(source))
    asyncio.run(run())
