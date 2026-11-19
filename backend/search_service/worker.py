"""Search indexer: consumes `search.index` events from RabbitMQ and upserts them into Elasticsearch."""
import asyncio
import logging

from search_service.application.ports.document_index import SearchBackendUnavailable
from search_service.infrastructure.messaging.index_broker import IndexBroker
from search_service.runtime import build_consumer, build_index

log = logging.getLogger('search_service.worker')


async def wait_for_index(index, delay=2.0):
    """The index (alias + mapping) must exist before the first bulk; ES may still be starting."""
    while True:
        try:
            return await index.ensure_index()
        except SearchBackendUnavailable as exc:
            log.warning('Waiting for Elasticsearch: %s', exc)
            await asyncio.sleep(delay)


async def run():
    index = build_index()
    log.info('Search index ready: %s', await wait_for_index(index))
    consumer = build_consumer(index)
    broker = await IndexBroker().connect()
    try:
        await broker.consume(consumer.handle)
    finally:
        await broker.close()
        await index.close()


if __name__ == '__main__':
    import logging.config
    import yaml
    with open('deploy/config/runtime-logging.yaml') as source:
        logging.config.dictConfig(yaml.safe_load(source))
    asyncio.run(run())
