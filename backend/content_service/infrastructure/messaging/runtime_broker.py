"""AMQP transport: durable queues, publisher confirms and bounded redelivery."""
import asyncio
import json
import logging
import os
from uuid import UUID
import aio_pika
from content_service.application.ports.corpus_store import StoreUnavailable

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 5
MAX_OUTAGE_PAUSE_SECONDS = 5  # short enough that writing resumes soon after the shard returns


class Broker:
    QUEUES = ('corpus.store', 'corpus.completed')

    def __init__(self, queues=None, concurrency: int = 1):
        if concurrency < 1:
            raise ValueError('Concurrency must be positive')
        self.queues = tuple(queues or self.QUEUES)
        self.concurrency = concurrency
        self._outages = 0

    async def connect(self):
        self.connection = await aio_pika.connect_robust(os.environ['BROKER_URL'])
        self.channel = await self.connection.channel(publisher_confirms=True, on_return_raises=True)
        # Consuming has its own channel: waiting for publisher confirms never delays deliveries or acks.
        self.consumer_channel = await self.connection.channel()
        await self.consumer_channel.set_qos(prefetch_count=self.concurrency)
        for name in self.queues:
            await self.channel.declare_queue(name + '.failed', durable=True)
            await self.channel.declare_queue(name, durable=True)
        return self

    async def publish(self, queue, payload, attempt=0):
        await self.channel.default_exchange.publish(aio_pika.Message(
            json.dumps(payload).encode(), content_type='application/json',
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            message_id=payload.get('event_id') or payload.get('batch_id'), headers={'attempt': attempt}),
            routing_key=queue, mandatory=True, timeout=10)

    async def _republish(self, message, routing_key, headers):
        await self.channel.default_exchange.publish(aio_pika.Message(
            message.body, content_type='application/json', delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers=headers, message_id=message.message_id), routing_key=routing_key, mandatory=True, timeout=10)

    async def consume(self, queue_name, handler, on_failure=None):
        """Handle up to `concurrency` messages at once; prefetch bounds both the tasks and unacknowledged data."""
        queue = await self.consumer_channel.get_queue(queue_name)
        tasks: set[asyncio.Task] = set()
        try:
            async with queue.iterator() as iterator:
                async for message in iterator:
                    task = asyncio.create_task(self._process(queue_name, message, handler, on_failure))
                    tasks.add(task)
                    task.add_done_callback(tasks.discard)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _process(self, queue_name, message, handler, on_failure):
        payload = None
        try:
            payload = json.loads(message.body)
            if not isinstance(payload, dict):
                raise ValueError("Message body must be a JSON object")
            await handler(payload)
        except asyncio.CancelledError:
            raise
        except StoreUnavailable as exc:
            # Infrastructure outage: the attempt counter is untouched, so valid data is never quarantined.
            self._outages = min(self._outages + 1, 10)
            log.warning('Store unavailable, batch requeued queue=%s id=%s: %s', queue_name, message.message_id, exc)
            await asyncio.sleep(min(2 ** (self._outages - 1), MAX_OUTAGE_PAUSE_SECONDS))
            await self._requeue(message)
        except Exception as exc:
            log.exception('Batch processing failed queue=%s id=%s', queue_name, message.message_id)
            await self._reject(queue_name, message, payload, exc, on_failure)
        else:
            self._outages = 0
            await self._ack(message)

    async def _ack(self, message):
        try:
            await message.ack()
        except Exception:
            # A lost channel redelivers the message; its committed receipt makes the repeat harmless.
            log.exception('Acknowledgement failed id=%s; the broker will redeliver', message.message_id)

    async def _requeue(self, message):
        try:
            if not message.processed:
                await message.nack(requeue=True)
        except Exception:
            log.exception('Requeue failed id=%s; the broker will redeliver', message.message_id)

    async def _reject(self, queue_name, message, payload, exc, on_failure):
        try:
            attempt = max(0, int((message.headers or {}).get('attempt', 0))) + 1
        except (ValueError, TypeError, OverflowError):
            attempt = 1
        try:
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(min(attempt, 3))
                await self._republish(message, queue_name, {'attempt': attempt})
            else:
                await self._republish(message, queue_name + '.failed', {'attempt': attempt, 'error': str(exc)[:500]})
                # Poison messages without valid correlation IDs cannot update a job.
                correlated = False
                if isinstance(payload, dict):
                    try:
                        UUID(str(payload['job_id'])); UUID(str(payload['batch_id']))
                        correlated = True
                    except (KeyError, ValueError, TypeError):
                        pass
                if on_failure and correlated:
                    await on_failure(payload, str(exc))
            await message.ack()
        except Exception:
            await self._requeue(message)
            await asyncio.sleep(2)

    async def close(self):
        await self.connection.close()
