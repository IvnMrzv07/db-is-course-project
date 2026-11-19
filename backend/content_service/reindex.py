"""Full search reindex (backfill): Content streams its own MongoDB corpus and publishes `search.index` events.

Search never reads MongoDB; it rebuilds only from broker events. The command is re-runnable: the indexer
upserts by document id with the owner's version as external version, so repeated runs do not duplicate.

    python -m content_service.reindex [--scope all|kaggle-cs|synthetic-cs] [--batch-size 100] [--evidence out.json]
"""
import argparse
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from uuid import uuid4
from pymongo import AsyncMongoClient
from content_service.application.services.commands.search_index_events import index_event
from content_service.infrastructure.messaging.runtime_broker import Broker
from contracts.messages import SEARCH_INDEX_QUEUE

log = logging.getLogger('content_service.reindex')
SCOPES = ('kaggle-cs', 'synthetic-cs')


def backfill_filter(scope: str) -> dict:
    if scope not in ('all', *SCOPES):
        raise ValueError('Unknown corpus scope')
    return {'publication_status': 'published', 'corpus_scope': {'$in': list(SCOPES)} if scope == 'all' else scope}


async def backfill(collection, publish, *, scope='all', batch_size=100, window=8, run_id=None):
    """Read documents in `_id` order and publish one event per `batch_size` documents (bounded concurrency)."""
    if not 1 <= batch_size <= 500:
        raise ValueError('batch_size must be 1..500')
    run_id = run_id or uuid4().hex[:12]
    started, published_documents, events, pending, chunk = time.perf_counter(), 0, 0, set(), []
    by_scope: dict[str, int] = {}

    async def flush():
        nonlocal events, published_documents
        event = index_event(f'{run_id}:{events:05d}', chunk, origin='backfill', event_id=f'backfill:{run_id}:{events:05d}')
        events += 1
        published_documents += len(event['documents'])
        for document in event['documents']:
            by_scope[document['corpus_scope']] = by_scope.get(document['corpus_scope'], 0) + 1
        pending.add(asyncio.create_task(publish(event)))
        if len(pending) >= window:
            done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            pending.difference_update(done)
            for task in done:
                task.result()

    cursor = collection.find(backfill_filter(scope), {'stored_at': 0, 'retrieved_at': 0}).sort('_id', 1).batch_size(1000)
    async for document in cursor:
        chunk.append(document)
        if len(chunk) == batch_size:
            await flush()
            chunk = []
            if events % 100 == 0:
                log.info('Backfill progress run=%s events=%s documents=%s', run_id, events, published_documents)
    if chunk:
        await flush()
    for task in pending:
        await task
    return {'run_id': run_id, 'scope': scope, 'batch_size': batch_size, 'events': events,
            'documents': published_documents, 'documents_by_scope': dict(sorted(by_scope.items())),
            'publish_seconds': round(time.perf_counter() - started, 3)}


async def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', default='all', choices=('all', *SCOPES))
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--evidence', help='write a JSON summary to this path')
    options = parser.parse_args(arguments)
    client = AsyncMongoClient(os.environ['MONGO_URL'], serverSelectionTimeoutMS=5000, tz_aware=True)
    broker = await Broker((SEARCH_INDEX_QUEUE,)).connect()
    try:
        collection = client.get_database('content').source_documents
        source_total = await collection.count_documents(backfill_filter(options.scope))
        summary = await backfill(collection, lambda event: broker.publish(SEARCH_INDEX_QUEUE, event),
                                 scope=options.scope, batch_size=options.batch_size)
        summary.update(source_documents=source_total, finished_at=datetime.now(timezone.utc).isoformat())
    finally:
        await broker.close()
        await client.close()
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    print(text)
    if options.evidence:
        with open(options.evidence, 'w', encoding='utf-8') as target:
            target.write(text + '\n')
    return summary


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    asyncio.run(main())
