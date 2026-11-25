"""Mongo persistence for the stage 9–12 corpus; transactions are scoped per batch."""
import asyncio
import re
from datetime import datetime, timezone, timedelta
from uuid import UUID
from pymongo.errors import PyMongoError
from content_service.application.dtos.document_query import DocumentQuery
from content_service.application.ports.corpus_store import StoreUnavailable
from content_service.application.services.commands.search_index_events import index_event
from content_service.infrastructure.database.availability import is_unavailable
from contracts.load_ids import LOAD_SCOPE
from contracts.messages import SEARCH_INDEX_QUEUE

# One counter document per scope makes concurrent batch transactions conflict on it (measured: 4 writers were
# slower than 1). Each batch increments one of these slots instead; readers sum them.
COUNTER_SLOTS = 64
# Sent outbox rows are only kept for inspection; without a TTL they grow with the corpus.
OUTBOX_SENT_TTL_SECONDS = 24 * 3600
BASE_INDEXES = ((('corpus_scope', 1), ('publication_status', 1), ('_id', 1)),
                (('corpus_scope', 1), ('metadata.document_type', 1), ('_id', 1)))
DOMAIN_INDEXES = tuple(((f'metadata.{field}', 1), ('_id', 1)) for field in ('tournament', 'team1', 'team2', 'played_at'))
# "Lean" domain indexes skip load documents: fewer B-trees per write. Chosen when the store is (re)created.
LEAN_SUFFIX = '_factual'
SNAPSHOT_FIELDS = ('snapshot_sha256', 'template_version')
CORPUS_SCOPES = ('kaggle-cs', 'synthetic-cs', LOAD_SCOPE)
# Load documents are not searched, and their index events would copy every text once more into the outbox.
INDEXED_SCOPES = ('kaggle-cs', 'synthetic-cs')
# Driver-side limit of one batch transaction. `with_transaction` alone retries for 120 s when a shard is absent,
# whatever timeout is configured on the client (measured), and would hold every consumer slot that long.
COMMIT_TIMEOUT_SECONDS = 20
LOAD_COUNT_LIMIT = 10_000  # filtered `load-cs` lists count at most this many matches


def counter_id(scope: str, batch_id: str) -> str:
    """Deterministic slot of a batch: a retried transaction touches the same document."""
    return f'{scope}#{UUID(batch_id).int % COUNTER_SLOTS:02d}'


def counters_by_scope(rows) -> dict:
    """Sum slot documents (`scope#NN`) with the per-scope base document (`scope`)."""
    totals: dict[str, int] = {}
    for row in rows:
        scope = row['_id'].split('#', 1)[0]
        totals[scope] = totals.get(scope, 0) + row['stored_documents']
    return totals


def require_same_snapshot(existing: dict, document: dict) -> None:
    known = existing.get('metadata') or {}
    if any(known.get(field) != document['metadata'].get(field) for field in SNAPSHOT_FIELDS):
        raise ValueError('Existing document belongs to another snapshot/template; migration required')


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
    def __init__(self, database, *, index_events: bool = False, index_scopes=INDEXED_SCOPES,
                 commit_timeout: float = COMMIT_TIMEOUT_SECONDS):
        self.db = database
        self.documents = database.source_documents
        # When enabled (cs-sharded stand), every committed batch also stages a `search.index` event
        # in the same transaction, so the search index can never miss a committed document.
        self.index_events = index_events
        self.index_scopes = frozenset(index_scopes)
        self.commit_timeout = commit_timeout

    async def initialize(self, *, lean_indexes: bool | None = None):
        if lean_indexes is None:  # services keep whichever profile the store was created with
            lean_indexes = any(name.endswith(LEAN_SUFFIX) for name in await self.documents.index_information())
        for fields in BASE_INDEXES:
            await self.documents.create_index(list(fields))
        for fields in DOMAIN_INDEXES:
            options = {'name': '_'.join(f'{field}_{order}' for field, order in fields) + LEAN_SUFFIX,
                       'partialFilterExpression': {'corpus_scope': {'$in': list(INDEXED_SCOPES)}}} if lean_indexes else {}
            await self.documents.create_index(list(fields), **options)
        await self.db.committed_batches.create_index([('committed_at', 1)])
        await self.db.outbox.create_index([('sent', 1)])
        await self.db.outbox.create_index([('sent_at', 1)], expireAfterSeconds=OUTBOX_SENT_TTL_SECONDS)
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
        for scope in CORPUS_SCOPES:
            await self.db.corpus_counters.update_one({'_id':scope}, {'$setOnInsert':{'stored_documents':0}}, upsert=True)

    async def browse(self, query):
        where = mongo_filter(query)
        offset = (query.page - 1) * query.page_size
        # With a shard absent the others still answer; mongos reports the gap instead of failing the list.
        reply = await self.db.command({'find': 'source_documents', 'filter': where, 'projection': {'text': 0},
            'sort': {'_id': 1}, 'skip': offset, 'limit': query.page_size, 'singleBatch': True,
            'allowPartialResults': True, 'maxTimeMS': 2000})
        items = [public(d) for d in reply['cursor']['firstBatch']]
        degraded = bool(reply['cursor'].get('partialResultsReturned'))
        total = await self._degraded_total(query, offset + len(items)) if degraded else await self._total(query, where)
        return {'items': items, 'total': total, 'page': query.page, 'page_size': query.page_size, 'degraded': degraded}

    async def _counters(self):
        return counters_by_scope([row async for row in self.db.corpus_counters.find({}, max_time_ms=2000)])

    async def _total(self, query, where):
        """Counting millions of load documents does not fit the read time limit: use counters or a bounded count."""
        if query.corpus_scope != LOAD_SCOPE:
            return await self.documents.count_documents(where, maxTimeMS=2000)
        if query.is_whole_scope:
            return (await self._counters()).get(LOAD_SCOPE, 0)
        return await self.documents.count_documents(where, limit=LOAD_COUNT_LIMIT, maxTimeMS=2000)

    async def _degraded_total(self, query, seen):
        """An exact count needs every shard: use the counters if they are reachable, otherwise what was returned."""
        if not query.is_whole_scope:
            return seen
        try:
            return (await self._counters()).get(query.corpus_scope, 0)
        except PyMongoError:
            return seen

    async def read(self, document_id: UUID):
        return public(await self.documents.find_one({'_id': str(document_id), 'publication_status': 'published'}, max_time_ms=2000))

    async def statistics(self):
        now = datetime.now(timezone.utc)
        samples = await self.db.committed_batches.aggregate([
            {'$match': {'committed_at': {'$gte': now - timedelta(seconds=10)}}},
            {'$group': {'_id': None, 'inserted': {'$sum': '$inserted'}}}], maxTimeMS=2000)
        rows = await samples.to_list()
        # Slots are summed per corpus scope; the total keeps its stage 9-12 meaning for kaggle-only stacks.
        counters = await self._counters()
        return {'stored_documents': sum(counters.values()), 'stored_by_scope': counters,
                'durable_documents_per_second': (rows[0]['inserted'] if rows else 0) / 10,
                'sampled_at': now.isoformat()}

    async def persist_batch(self, batch):
        async def transaction(session):
            receipt = await self.db.committed_batches.find_one({'_id': batch['batch_id']}, session=session)
            if receipt:
                return receipt['result']
            now = datetime.now(timezone.utc)
            unique: dict[str, dict] = {}
            for source in batch['documents']:
                document = dict(source)
                document['_id'] = document.pop('id')
                document['retrieved_at'] = batch['prepared_at']
                document['stored_at'] = now
                # The same ID twice in one batch is a duplicate, exactly as if the first copy was already stored.
                require_same_snapshot(unique.setdefault(document['_id'], document), document)
            # One read and one bulk insert per batch. Two statements per document cost ~200 round trips through
            # mongos per 100 documents and limited a writer to ~1,000 documents/s.
            stored = set()
            async for existing in self.documents.find({'_id': {'$in': list(unique)}},
                                                      {f'metadata.{field}': 1 for field in SNAPSHOT_FIELDS}, session=session):
                require_same_snapshot(existing, unique[existing['_id']])
                stored.add(existing['_id'])
            new = [document for key, document in unique.items() if key not in stored]
            if new:
                await self.documents.insert_many(new, ordered=False, session=session)
            by_scope: dict[str, int] = {}
            for document in new:
                by_scope[document['corpus_scope']] = by_scope.get(document['corpus_scope'], 0) + 1
            inserted = len(new)
            result = {'job_id': batch['job_id'], 'batch_id': batch['batch_id'], 'checkpoint': batch['checkpoint'],
                      'inserted': inserted, 'duplicates': len(batch['documents']) - inserted, 'rejected': 0}
            for scope, count in sorted(by_scope.items()):
                await self.db.corpus_counters.update_one({'_id': counter_id(scope, batch['batch_id'])},
                    {'$inc': {'stored_documents': count}}, upsert=True, session=session)
            await self.db.committed_batches.insert_one({'_id': batch['batch_id'], 'committed_at': now,
                'inserted': inserted, 'result': result}, session=session)
            await self.db.outbox.insert_one({'_id': batch['batch_id'], 'payload': result, 'sent': False}, session=session)
            indexable = [d for d in batch['documents'] if d['corpus_scope'] in self.index_scopes] if self.index_events else []
            if indexable:
                # All batch documents (new and duplicate): indexing is idempotent by id + external version,
                # so a replay of an already stored snapshot also repairs a lagging or rebuilt index.
                await self.db.outbox.insert_one({'_id': 'index:' + batch['batch_id'], 'queue': SEARCH_INDEX_QUEUE,
                                                 'payload': index_event(batch['batch_id'], indexable, now=now),
                                                 'sent': False}, session=session)
            return result
        from pymongo.write_concern import WriteConcern
        from pymongo.read_concern import ReadConcern
        try:
            async with asyncio.timeout(self.commit_timeout):
                async with self.db.client.start_session() as session:
                    return await session.with_transaction(transaction, read_concern=ReadConcern('snapshot'), write_concern=WriteConcern('majority'))
        except TimeoutError as exc:
            # The commit may still have succeeded: the retry then finds the receipt and repeats its result.
            raise StoreUnavailable(f'No commit within {self.commit_timeout} s') from exc
        except PyMongoError as exc:
            if is_unavailable(exc):
                raise StoreUnavailable(f'{type(exc).__name__}: {str(exc)[:200]}') from exc
            raise

    async def unsent(self, limit):
        return [row async for row in self.db.outbox.find({'sent': False}).limit(limit)]

    async def mark_sent(self, rows):
        """Confirmed by the broker: completions are marked, index events (they carry document text) are removed."""
        finished = [row['_id'] for row in rows if row.get('queue') == SEARCH_INDEX_QUEUE]
        marked = [row['_id'] for row in rows if row.get('queue') != SEARCH_INDEX_QUEUE]
        if finished:
            await self.db.outbox.delete_many({'_id': {'$in': finished}})
        if marked:
            await self.db.outbox.update_many({'_id': {'$in': marked}},
                                             {'$set': {'sent': True, 'sent_at': datetime.now(timezone.utc)}})
