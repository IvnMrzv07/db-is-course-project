"""AMQP consumer for `search.index`: ack only after the bulk upsert succeeded.

* Elasticsearch unavailable (SearchBackendUnavailable) -> nack+requeue after a growing pause; the attempt
  counter is NOT increased, so an ES outage delays indexing but never quarantines valid events.
* Invalid event (validation/mapping error) -> republish with attempt+1, after 5 attempts move to
  `search.index.failed` (same quarantine rule as corpus queues).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

import aio_pika

from contracts.messages import SEARCH_INDEX_QUEUE
from search_service.application.ports.document_index import SearchBackendUnavailable

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


class IndexBroker:
    def __init__(self, url: str | None = None, queue: str = SEARCH_INDEX_QUEUE, prefetch: int = 4):
        self.url, self.queue_name, self.prefetch = url or os.environ['BROKER_URL'], queue, prefetch

    async def connect(self):
        self.connection = await aio_pika.connect_robust(self.url)
        self.channel = await self.connection.channel(publisher_confirms=True, on_return_raises=True)
        await self.channel.set_qos(prefetch_count=self.prefetch)
        await self.channel.declare_queue(self.queue_name + '.failed', durable=True)
        self.queue = await self.channel.declare_queue(self.queue_name, durable=True)
        return self

    async def _republish(self, message, routing_key: str, headers: dict):
        await self.channel.default_exchange.publish(aio_pika.Message(
            message.body, content_type='application/json', delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers=headers, message_id=message.message_id), routing_key=routing_key, mandatory=True, timeout=10)

    async def consume(self, handler):
        outage = 0
        async with self.queue.iterator() as iterator:
            async for message in iterator:
                try:
                    payload = json.loads(message.body)
                    if not isinstance(payload, dict):
                        raise ValueError('Message body must be a JSON object')
                    await handler(payload)
                except asyncio.CancelledError:
                    raise
                except SearchBackendUnavailable as exc:
                    outage = min(outage + 1, 6)
                    log.warning('Search backend unavailable, event requeued id=%s: %s', message.message_id, exc)
                    await asyncio.sleep(min(2 ** outage, 30))
                    if not message.processed:
                        await message.nack(requeue=True)
                    continue
                except Exception as exc:
                    log.exception('Index event rejected id=%s', message.message_id)
                    try:
                        attempt = max(0, int((message.headers or {}).get('attempt', 0))) + 1
                    except (TypeError, ValueError, OverflowError):
                        attempt = 1
                    try:
                        if attempt < MAX_ATTEMPTS:
                            await asyncio.sleep(min(attempt, 3))
                            await self._republish(message, self.queue_name, {'attempt': attempt})
                        else:
                            await self._republish(message, self.queue_name + '.failed',
                                                  {'attempt': attempt, 'error': str(exc)[:500]})
                        await message.ack()
                    except Exception:
                        if not message.processed:
                            await message.nack(requeue=True)
                        await asyncio.sleep(2)
                    continue
                outage = 0
                await message.ack()

    async def close(self):
        await self.connection.close()
