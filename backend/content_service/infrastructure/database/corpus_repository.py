"""Mongo persistence for the stage 9–12 corpus; transactions are scoped per batch."""
import re
from datetime import datetime, timezone, timedelta
from uuid import UUID
from content_service.application.dtos.document_query import DocumentQuery
from content_service.application.services.commands.search_index_events import index_event
from contracts.messages import SEARCH_INDEX_QUEUE


def mongo_filter(query: DocumentQuery) -> dict:
    result = {"corpus_scope": query.corpus_scope, "publication_status": "published"}
    conditions = []
    if query.q.strip():
        literal = {"$regex": re.escape(query.q.strip()), "$options": "i"}
        conditions.append({"$or": [{"title": literal}, {"text": literal}]})
    if query.document_type:
        result["metadata.document_type"] = query.document_type
    if query.tournament:
        result["metadata.tournament"] = query.tournament
    if query.team:
        conditions.append({"$or": [{"metadata.team1": query.team}, {"metadata.team2": query.team}]})
    if query.date_from or query.date_to:
        bounds = {}
        if query.date_from:
            bounds["$gte"] = query.date_from
        if query.date_to:
            bounds["$lt"] = (datetime.fromisoformat(query.date_to) + timedelta(days=1)).date().isoformat()
        result["metadata.played_at"] = bounds
    if conditions:
        result["$and"] = conditions
    return result


def public(document):
    if document is None:
        return None
    return {**{k: v for k, v in document.items() if k != "_id"}, "id": document["_id"]}


class MongoCorpusRepository:
    def __init__(self, database, *, index_events: bool = False):
        self.db = database
        self.documents = database.source_documents
        # When enabled (cs-sharded stand), every committed batch also stages a `search.index` event
        # in the same transaction, so the search index can never miss a committed document.
        self.index_events = index_events

    async def initialize(self):
        for fields in ([('corpus_scope', 1), ('publication_status', 1), ('_id', 1)],
                       [('corpus_scope', 1), ('metadata.document_type', 1), ('_id', 1)],
                       [('metadata.tournament', 1), ('_id', 1)],
                       [('metadata.team1', 1), ('_id', 1)], [('metadata.team2', 1), ('_id', 1)],
                       [('metadata.played_at', 1), ('_id', 1)]):
            await self.documents.create_index(fields)
        await self.db.committed_batches.create_index([('committed_at', 1)])
        await self.db.outbox.create_index([('sent', 1)])
        # Pre-create collections before the first transaction.
        for name in ('source_documents', 'committed_batches', 'outbox', 'corpus_counters'):
            if name not in await self.db.list_collection_names():
                from pymongo.errors import CollectionInvalid, OperationFailure
                try:
                    await self.db.create_collection(name)
                except CollectionInvalid:
                    pass
                except OperationFailure as exc:
                    if exc.code != 48:
                        raise
        for scope in ('kaggle-cs', 'synthetic-cs'):
            await self.db.corpus_counters.update_one({'_id':scope}, {'$setOnInsert':{'stored_documents':0}}, upsert=True)

    async def browse(self, query):
        where = mongo_filter(query)
        total = await self.documents.count_documents(where, maxTimeMS=2000)
        cursor = self.documents.find(where, {'text': 0}).sort('_id', 1).skip((query.page - 1) * query.page_size).limit(query.page_size).max_time_ms(2000)
        return {'items': [public(d) async for d in cursor], 'total': total, 'page': query.page, 'page_size': query.page_size}

    async def read(self, document_id: UUID):
        return public(await self.documents.find_one({'_id': str(document_id), 'publication_status': 'published'}, max_time_ms=2000))

    async def statistics(self):
        now = datetime.now(timezone.utc)
        samples = await self.db.committed_batches.aggregate([
            {'$match': {'committed_at': {'$gte': now - timedelta(seconds=10)}}},
            {'$group': {'_id': None, 'inserted': {'$sum': '$inserted'}}}], maxTimeMS=2000)
        rows = await samples.to_list()
        # One counter document per corpus scope; the total keeps its stage 9-12 meaning for kaggle-only stacks.
        counters = {row['_id']: row['stored_documents'] async for row in self.db.corpus_counters.find({}, max_time_ms=2000)}
        return {'stored_documents': sum(counters.values()), 'stored_by_scope': counters,
                'durable_documents_per_second': (rows[0]['inserted'] if rows else 0) / 10,
                'sampled_at': now.isoformat()}

    async def persist_batch(self, batch):
        async def transaction(session):
            receipt = await self.db.committed_batches.find_one({'_id': batch['batch_id']}, session=session)
            if receipt:
                return receipt['result']
            inserted, by_scope = 0, {}
            now = datetime.now(timezone.utc)
            for source in batch['documents']:
                document = dict(source)
                document['_id'] = document.pop('id')
                document['retrieved_at'] = batch['prepared_at']
                document['stored_at'] = now
                existing = await self.documents.find_one({'_id':document['_id']}, {'metadata.snapshot_sha256':1,'metadata.template_version':1}, session=session)
                if existing and any(existing['metadata'].get(k) != document['metadata'].get(k) for k in ('snapshot_sha256','template_version')):
                    raise ValueError('Existing document belongs to another snapshot/template; migration required')
                result = await self.documents.update_one({'_id': document['_id']}, {'$setOnInsert': document}, upsert=True, session=session)
                if result.upserted_id is not None:
                    inserted += 1
                    by_scope[document['corpus_scope']] = by_scope.get(document['corpus_scope'], 0) + 1
            result = {'job_id': batch['job_id'], 'batch_id': batch['batch_id'], 'checkpoint': batch['checkpoint'],
                      'inserted': inserted, 'duplicates': len(batch['documents']) - inserted, 'rejected': 0}
            for scope, count in sorted(by_scope.items()):
                await self.db.corpus_counters.update_one({'_id':scope}, {'$inc':{'stored_documents':count}}, upsert=True, session=session)
            await self.db.committed_batches.insert_one({'_id': batch['batch_id'], 'committed_at': now,
                'inserted': inserted, 'result': result}, session=session)
            await self.db.outbox.insert_one({'_id': batch['batch_id'], 'payload': result, 'sent': False}, session=session)
            if self.index_events:
                # All batch documents (new and duplicate): indexing is idempotent by id + external version,
                # so a replay of an already stored snapshot also repairs a lagging or rebuilt index.
                await self.db.outbox.insert_one({'_id': 'index:' + batch['batch_id'], 'queue': SEARCH_INDEX_QUEUE,
                                                 'payload': index_event(batch['batch_id'], batch['documents'], now=now),
                                                 'sent': False}, session=session)
            return result
        async with self.db.client.start_session() as session:
            from pymongo.write_concern import WriteConcern
            from pymongo.read_concern import ReadConcern
            return await session.with_transaction(transaction, read_concern=ReadConcern('snapshot'), write_concern=WriteConcern('majority'))
