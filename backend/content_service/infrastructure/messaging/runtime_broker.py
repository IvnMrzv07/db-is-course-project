"""AMQP transport: durable queues, publisher confirms and bounded redelivery."""
import asyncio
import json
import logging
import os
from uuid import UUID
import aio_pika

log = logging.getLogger(__name__)

class Broker:
    QUEUES = ('corpus.store', 'corpus.completed')

    def __init__(self, queues=None):
        self.queues = tuple(queues or self.QUEUES)

    async def connect(self):
        self.connection = await aio_pika.connect_robust(os.environ['BROKER_URL'])
        self.channel = await self.connection.channel(publisher_confirms=True, on_return_raises=True)
        await self.channel.set_qos(prefetch_count=1)
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

    async def consume(self, queue_name, handler, on_failure=None):
        queue = await self.channel.get_queue(queue_name)
        async with queue.iterator() as iterator:
            async for message in iterator:
                payload = None
                try:
                    payload = json.loads(message.body)
                    if not isinstance(payload, dict):
                        raise ValueError("Message body must be a JSON object")
                    await handler(payload)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.exception('Batch processing failed queue=%s id=%s',queue_name,message.message_id)
                    try:
                        attempt = max(0, int(message.headers.get('attempt', 0))) + 1
                    except (ValueError, TypeError, OverflowError):
                        attempt = 1
                    try:
                        if attempt < 5:
                            await asyncio.sleep(min(attempt, 3))
                            await self.channel.default_exchange.publish(aio_pika.Message(
                                message.body, content_type='application/json',
                                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                headers={'attempt':attempt}, message_id=message.message_id),
                                routing_key=queue_name, mandatory=True, timeout=10)
                        else:
                            await self.channel.default_exchange.publish(aio_pika.Message(
                                message.body, content_type='application/json',
                                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                                headers={'attempt':attempt,'error':str(exc)[:500]}, message_id=message.message_id),
                                routing_key=queue_name+'.failed', mandatory=True, timeout=10)
                            # Poison messages without valid correlation IDs cannot update a job.
                            correlated = False
                            if isinstance(payload, dict):
                                try:
                                    UUID(str(payload['job_id'])); UUID(str(payload['batch_id']))
                                    correlated = True
                                except (KeyError, ValueError, TypeError):
                                    pass
                            if on_failure and correlated:
                                await on_failure(payload,str(exc))
                        await message.ack()
                    except Exception:
                        if not message.processed:
                            await message.nack(requeue=True)
                        await asyncio.sleep(2)
                else:
                    await message.ack()

    async def close(self):
        await self.connection.close()
