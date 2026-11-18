"""Run inside ingestion_api after imports finish; redeliver an existing batch/event."""
import asyncio
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit

import asyncpg
import httpx
from pymongo import AsyncMongoClient
from ingestion_service.infrastructure.messaging.runtime_broker import Broker


async def main():
    pool = await asyncpg.create_pool(os.environ['INGESTION_DATABASE_URL'])
    mongo = AsyncMongoClient(os.environ['MONGO_URL'])
    broker = await Broker().connect()
    try:
        assert await pool.fetchval("SELECT count(*) FROM replay_jobs WHERE status IN ('running','paused')") == 0
        payload = json.loads(await pool.fetchval('SELECT payload FROM replay_outbox ORDER BY created_at LIMIT 1'))
        receipt = await mongo.content.committed_batches.find_one({'_id': payload['batch_id']})
        before_jobs = await pool.fetch('SELECT id,inserted,duplicates,rejected,checkpoint,status FROM replay_jobs ORDER BY id')
        before_count = await mongo.content.source_documents.count_documents({})
        before_receipts = await mongo.content.committed_batches.count_documents({})
        for _ in range(2):
            await broker.publish('corpus.store', payload)
            await broker.publish('corpus.completed', receipt['result'])
        url = urlsplit(os.environ['BROKER_URL'])
        async with httpx.AsyncClient(base_url=f'http://{url.hostname}:15672', auth=(url.username, url.password)) as client:
            for _ in range(30):
                await asyncio.sleep(1)
                response = await client.get('/api/queues/%2F')
                response.raise_for_status()
                queues = response.json()
                if all(q.get('messages', 1) == 0 for q in queues) and _ >= 6:
                    break
            else:
                raise AssertionError('RabbitMQ queues did not drain')
        assert await mongo.content.source_documents.count_documents({}) == before_count
        assert await mongo.content.committed_batches.count_documents({}) == before_receipts
        assert await pool.fetch('SELECT id,inserted,duplicates,rejected,checkpoint,status FROM replay_jobs ORDER BY id') == before_jobs
        print(json.dumps({'verified_at': datetime.now(timezone.utc).isoformat(),
                          'stored_documents': before_count, 'redelivered_batch_id': payload['batch_id'],
                          'store_redeliveries': 2, 'completion_redeliveries': 2,
                          'document_receipt_and_job_counts_unchanged': True,
                          'queues': {q['name']: q['messages'] for q in queues}}, indent=2))
    finally:
        await broker.close()
        await mongo.close()
        await pool.close()


asyncio.run(main())
