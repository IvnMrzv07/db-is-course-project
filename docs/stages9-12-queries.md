# Stages 9–12 query catalogue

## MongoDB queries

All queries target Content-owned collections, use sessions for batch writes and bounded execution for public reads. `_id` is a stable UUID string. No sharding or partitioning commands are issued.

### Public reads and filters

`GET /documents?q=Alpha&document_type=map&page=1&page_size=20` returns `{items, total, page, page_size}`. `GET /documents/{id}` returns the full document or 404. Literal search is escaped before `$regex` with option `i`. Dates include the full end date. Exact team matching covers both team fields.


### content_service/infrastructure/database/corpus_repository.py — mongo_filter

```python
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
```

### content_service/infrastructure/database/corpus_repository.py — initialize

```python
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
        await self.db.corpus_counters.update_one({'_id':'kaggle-cs'}, {'$setOnInsert':{'stored_documents':0}}, upsert=True)
```

### content_service/infrastructure/database/corpus_repository.py — browse

```python
async def browse(self, query):
        where = mongo_filter(query)
        total = await self.documents.count_documents(where, maxTimeMS=2000)
        cursor = self.documents.find(where, {'text': 0}).sort('_id', 1).skip((query.page - 1) * query.page_size).limit(query.page_size).max_time_ms(2000)
        return {'items': [public(d) async for d in cursor], 'total': total, 'page': query.page, 'page_size': query.page_size}
```

### content_service/infrastructure/database/corpus_repository.py — read

```python
async def read(self, document_id: UUID):
        return public(await self.documents.find_one({'_id': str(document_id), 'publication_status': 'published'}, max_time_ms=2000))
```

### content_service/infrastructure/database/corpus_repository.py — statistics

```python
async def statistics(self):
        now = datetime.now(timezone.utc)
        samples = await self.db.committed_batches.aggregate([
            {'$match': {'committed_at': {'$gte': now - timedelta(seconds=10)}}},
            {'$group': {'_id': None, 'inserted': {'$sum': '$inserted'}}}], maxTimeMS=2000)
        rows = await samples.to_list()
        counter = await self.db.corpus_counters.find_one({'_id':'kaggle-cs'}, max_time_ms=2000)
        return {'stored_documents': counter['stored_documents'] if counter else 0,
                'durable_documents_per_second': (rows[0]['inserted'] if rows else 0) / 10,
                'sampled_at': now.isoformat()}
```

### content_service/infrastructure/database/corpus_repository.py — persist_batch

```python
async def persist_batch(self, batch):
        async def transaction(session):
            receipt = await self.db.committed_batches.find_one({'_id': batch['batch_id']}, session=session)
            if receipt:
                return receipt['result']
            inserted = 0
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
                inserted += int(result.upserted_id is not None)
            result = {'job_id': batch['job_id'], 'batch_id': batch['batch_id'], 'checkpoint': batch['checkpoint'],
                      'inserted': inserted, 'duplicates': len(batch['documents']) - inserted, 'rejected': 0}
            await self.db.corpus_counters.update_one({'_id':'kaggle-cs'}, {'$inc':{'stored_documents':inserted}}, session=session)
            await self.db.committed_batches.insert_one({'_id': batch['batch_id'], 'committed_at': now,
                'inserted': inserted, 'result': result}, session=session)
            await self.db.outbox.insert_one({'_id': batch['batch_id'], 'payload': result, 'sent': False}, session=session)
            return result
        async with self.db.client.start_session() as session:
            from pymongo.write_concern import WriteConcern
            from pymongo.read_concern import ReadConcern
            return await session.with_transaction(transaction, read_concern=ReadConcern('snapshot'), write_concern=WriteConcern('majority'))
```

### content_service/worker.py — dispatch

```python
async def dispatch():
        while True:
            try:
                async for row in repository.db.outbox.find({'sent':False}).limit(100):
                    await broker.publish('corpus.completed', row['payload'])
                    await repository.db.outbox.update_one({'_id':row['_id']},{'$set':{'sent':True}})
            except Exception:
                logging.exception('Content outbox dispatch failed; retained for retry')
            await asyncio.sleep(.1)
```

## PostgreSQL queries

DDL and constraints: `ingestion_service/infrastructure/database/migrations/001_replay.sql`. Parameters are bound by asyncpg.

### ingestion_service/infrastructure/database/replay_store.py:71

```sql
SELECT * FROM replay_jobs ORDER BY created_at DESC,id LIMIT $1 OFFSET $2
```

### ingestion_service/infrastructure/database/replay_store.py:68

```sql
SELECT * FROM replay_jobs WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:72

```sql
SELECT count(*) FROM replay_jobs
```

### ingestion_service/infrastructure/database/replay_store.py:20

```sql
SELECT pg_advisory_xact_lock(912001)
```

### ingestion_service/infrastructure/database/replay_store.py:57

```sql
INSERT INTO replay_jobs
                  (id,idempotency_key,request_hash,snapshot_id,snapshot_hash,total,status,target_rate,validation_rejected)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT(idempotency_key) DO NOTHING
```

### ingestion_service/infrastructure/database/replay_store.py:62

```sql
SELECT * FROM replay_jobs WHERE idempotency_key=$1
```

### ingestion_service/infrastructure/database/replay_store.py:77

```sql
SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE
```

### ingestion_service/infrastructure/database/replay_store.py:85

```sql
UPDATE replay_jobs SET status=$2,target_rate=$3,next_at=now(),updated_at=now() WHERE id=$1 RETURNING *
```

### ingestion_service/infrastructure/database/replay_store.py:92

```sql
SELECT * FROM replay_jobs WHERE status='running' AND produced<total
                    AND next_at<=now() AND produced-inserted-duplicates-rejected<1000
                    ORDER BY next_at LIMIT 1 FOR UPDATE SKIP LOCKED
```

### ingestion_service/infrastructure/database/replay_store.py:108

```sql
INSERT INTO replay_batches(id,job_id,start_offset,end_offset) VALUES($1,$2,$3,$4)
```

### ingestion_service/infrastructure/database/replay_store.py:109

```sql
INSERT INTO replay_outbox(id,payload) VALUES($1,$2::jsonb)
```

### ingestion_service/infrastructure/database/replay_store.py:110

```sql
UPDATE replay_jobs SET produced=$2,next_at=$3,updated_at=now() WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:119

```sql
SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE
```

### ingestion_service/infrastructure/database/replay_store.py:120

```sql
SELECT * FROM replay_batches WHERE id=$1 AND job_id=$2 FOR UPDATE
```

### ingestion_service/infrastructure/database/replay_store.py:132

```sql
UPDATE replay_batches SET status='completed' WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:133

```sql
SELECT min(start_offset) FROM replay_batches WHERE job_id=$1 AND status!='completed'
```

### ingestion_service/infrastructure/database/replay_store.py:136

```sql
UPDATE replay_jobs SET inserted=inserted+$2,duplicates=duplicates+$3,rejected=rejected+$4,checkpoint=$5,status=$6,updated_at=now() WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:99

```sql
UPDATE replay_jobs SET status='failed',error='Snapshot changed',updated_at=now() WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:126

```sql
UPDATE replay_batches SET status='failed' WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:127

```sql
UPDATE replay_jobs SET status='failed',error=$2,updated_at=now() WHERE id=$1
```

### ingestion_service/worker.py:22

```sql
SELECT id,payload FROM replay_outbox WHERE NOT sent ORDER BY created_at LIMIT 50 FOR UPDATE SKIP LOCKED
```

### ingestion_service/worker.py:25

```sql
UPDATE replay_outbox SET sent=true WHERE id=$1
```

### ingestion_service/presentation/api/app.py:54

```sql
SELECT 1
```
## Outcomes and indexes

Batch completion returns `{job_id, batch_id, checkpoint, inserted, duplicates, rejected}`. The sum of counts must match the batch size. Failed batches carry `error` instead of successful counts. `replay_batches(job_id,start_offset)` and job idempotency keys are unique. Pending batches/outbox entries have partial indexes. MongoDB has unique `_id`, filter indexes, a committed-time index and an outbox sent-state index.

## Manual reconciliation

```javascript
db.source_documents.countDocuments({corpus_scope:"kaggle-cs"})
db.corpus_counters.findOne({_id:"kaggle-cs"})
db.committed_batches.find({}, {result:1}).limit(5)
```

The first two counts must agree. The counter is updated transactionally; reconciliation is an acceptance check, not a one-second full scan.
