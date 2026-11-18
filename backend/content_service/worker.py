import asyncio
import logging
from content_service.runtime import build_runtime
from content_service.infrastructure.messaging.runtime_broker import Broker

async def run():
    client, repository, controller, commands = await build_runtime()
    broker = await Broker().connect()
    async def dispatch():
        while True:
            try:
                async for row in repository.db.outbox.find({'sent':False}).limit(100):
                    await broker.publish('corpus.completed', row['payload'])
                    await repository.db.outbox.update_one({'_id':row['_id']},{'$set':{'sent':True}})
            except Exception:
                logging.exception('Content outbox dispatch failed; retained for retry')
            await asyncio.sleep(.1)
    async def failed(batch,error):
        await broker.publish('corpus.completed',{'job_id':batch['job_id'],'batch_id':batch['batch_id'],'error':error})
    tasks = [asyncio.create_task(dispatch()),asyncio.create_task(broker.consume('corpus.store',commands.store,failed))]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await broker.close()
        await client.close()

if __name__ == '__main__':
    import logging.config, yaml
    with open('deploy/config/runtime-logging.yaml') as source:
        logging.config.dictConfig(yaml.safe_load(source))
    asyncio.run(run())
