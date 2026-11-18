import asyncio
import json
import logging
from ingestion_service.runtime import build_runtime
from ingestion_service.infrastructure.messaging.runtime_broker import Broker

async def run():
    pool, store, controller = await build_runtime()
    broker = await Broker().connect()
    async def produce():
        while True:
            try:
                await store.produce()
            except Exception:
                logging.exception('Producer failed; checkpoint retained')
            await asyncio.sleep(.01)
    async def dispatch():
        while True:
            try:
                async with pool.acquire() as connection:
                    async with connection.transaction():
                        rows = await connection.fetch('SELECT id,payload FROM replay_outbox WHERE NOT sent ORDER BY created_at LIMIT 50 FOR UPDATE SKIP LOCKED')
                        for row in rows:
                            await broker.publish('corpus.store',json.loads(row['payload']))
                            await connection.execute('UPDATE replay_outbox SET sent=true WHERE id=$1',row['id'])
            except Exception:
                logging.exception('Ingestion outbox dispatch failed; retained for retry')
            await asyncio.sleep(.05)
    tasks = [asyncio.create_task(produce()),asyncio.create_task(dispatch()),asyncio.create_task(broker.consume('corpus.completed',store.complete))]
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
