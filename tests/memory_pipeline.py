"""The whole write pipeline in one process: real stores and real worker functions around an in-memory AMQP double.

Only RabbitMQ itself is replaced; acknowledgement, requeue, prefetch and redelivery follow its semantics.
"""
import asyncio
import contextlib
import json
from collections import deque
from types import SimpleNamespace

from content_service.infrastructure.messaging.runtime_broker import Broker
from content_service.worker import dispatch_once


class MemoryMessage:
    def __init__(self, queue, body, headers, message_id):
        self.queue, self.body, self.headers, self.message_id = queue, body, headers, message_id
        self.processed = False

    async def ack(self):
        self._finish()

    async def nack(self, requeue):
        self._finish()
        if requeue:
            self.queue.put(self.body, self.headers, self.message_id)

    def _finish(self):
        assert not self.processed, 'message settled twice'
        self.processed = True
        self.queue.unacked -= 1
        self.queue.changed.set()


class MemoryQueue:
    def __init__(self, prefetch):
        self.ready, self.unacked, self.prefetch, self.changed = deque(), 0, prefetch, asyncio.Event()

    def put(self, body, headers, message_id):
        self.ready.append((body, headers, message_id))
        self.changed.set()

    def iterator(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        while not self.ready or self.unacked >= self.prefetch:
            self.changed.clear()
            await self.changed.wait()
        self.unacked += 1
        return MemoryMessage(self, *self.ready.popleft())


class MemoryBroker(Broker):
    def __init__(self, concurrency=4):
        super().__init__(concurrency=concurrency)
        self.memory = {name + suffix: MemoryQueue(concurrency if name == 'corpus.store' else 1)
                       for name in self.QUEUES for suffix in ('', '.failed')}

        async def get_queue(name):
            return self.memory[name]
        self.consumer_channel = SimpleNamespace(get_queue=get_queue)

    async def publish(self, queue, payload, attempt=0):
        self.memory[queue].put(json.dumps(payload).encode(), {'attempt': attempt}, payload.get('batch_id'))

    async def _republish(self, message, routing_key, headers):
        self.memory[routing_key].put(message.body, headers, message.message_id)

    @property
    def quarantined(self):
        return sum(len(queue.ready) for name, queue in self.memory.items() if name.endswith('.failed'))


@contextlib.asynccontextmanager
async def running_pipeline(store, repository, commands, concurrency=4):
    """Ingestion producer and dispatcher, Content consumer and dispatcher, completion consumer."""
    broker = MemoryBroker(concurrency)

    async def loop(step, idle):
        while True:
            try:
                busy = await step()
            except Exception:
                busy = 0
                await asyncio.sleep(.2)
            await asyncio.sleep(0 if busy else idle)

    async def failed(batch, error):
        await broker.publish('corpus.completed', {'job_id': batch['job_id'], 'batch_id': batch['batch_id'], 'error': error})
    tasks = [asyncio.create_task(task) for task in (
        loop(store.produce, .01), loop(lambda: store.dispatch(broker.publish), .02),
        loop(lambda: dispatch_once(repository, broker.publish), .05),
        broker.consume('corpus.store', commands.store, failed), broker.consume('corpus.completed', store.complete))]
    try:
        yield broker
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def wait_until(condition, timeout=60):
    async with asyncio.timeout(timeout):
        while not await condition():
            await asyncio.sleep(.1)
