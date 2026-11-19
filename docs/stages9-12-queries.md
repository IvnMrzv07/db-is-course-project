# Stages 9–12 query catalogue

## MongoDB queries

All queries target Content-owned collections, use sessions for batch writes and bounded execution for public reads. `_id` is a stable UUID string. The services issue no sharding or partitioning commands; in the optional sharded variant, sharding is configured by `deploy/mongo-sharded-init.sh`, not by Content.

### Public reads and filters

`GET /documents?q=Alpha&document_type=map&page=1&page_size=20` returns `{items, total, page, page_size}`. `GET /documents/{id}` returns the full document or 404. Literal search is escaped before `$regex` with option `i`. Dates include the full end date. Exact team matching covers both team fields. Every list query is restricted to one `corpus_scope` (`kaggle-cs` by default; `&corpus_scope=synthetic-cs` selects the generated load corpus), so factual and synthetic documents are never mixed in one result. `GET /corpus/statistics` returns `stored_documents` (sum over scopes) and `stored_by_scope`.

### Distributed map-reduce (`GET /distributed/map-reduce`)

Read-only aggregation over `metadata.template_version = "2"` documents of both scopes (`corpus_scope=all|kaggle-cs|synthetic-cs`, default `all`). Parameters: `metric`, `document_type`, `engine=aggregate|mapreduce|both`, `limit` (1–100, `top_players` only), `explain` (default `true`). The filter is `{corpus_scope: {$in: [...]} | scope, publication_status: "published", "metadata.template_version": "2", "metadata.document_type"?}`; on every shard it uses the `{corpus_scope, metadata.document_type, _id}` or `{corpus_scope, publication_status, _id}` index.

| `metric` | Documents | Group key | Raw sums |
|---|---|---|---|
| `map_pool` | `map` only (fixed) | `metadata.map_name` (null kept) | maps, scored, rounds, margin, team1/team2 wins, draws |
| `document_types` | optional type filter | `(corpus_scope, document_type)` | documents, with_players, player_rows, wins |
| `series_scores` | `series` only (fixed) | `(best_of, "max:min")` | documents, wins |
| `top_players` | `document_type` **required** | `metadata.players.player_id` after `$unwind` | name (`$max`), documents, kills, deaths, assists, ADR/KAST sum and count |

- Series totals already include their maps, so player and score metrics never mix the two types; `document_types` only counts them in separate rows. Invalid combinations return 422.
- `aggregate`: mongos splits the pipeline into `shardsPart` (`$match` + partial `$group`, i.e. map + combine) and `mergerPart` (`$mergeCursors` + merging `$group` + `$sort`; for `top_players` the `$limit` is folded into the sort).
- `mapreduce`: the `mapReduce` command with JavaScript map/reduce and `out: {inline: 1}`. MongoDB 7 runs it as `$_internalJsEmit` / `$_internalJsReduce` with the same split. It cannot sort or limit its output, so Content sorts and cuts it with the same order as the pipeline's `$sort`.
- Missing values are treated identically by both engines: missing score → not counted in `scored`/`rounds`; missing `map_name`/`best_of` → `null` key; non-numeric player stat → 0 and not counted in ADR/KAST averages.
- Derived indicators (averages, shares, K/D) are computed once in the application layer from the raw sums.
- Response: `rows`, `matched_documents` (`countDocuments` with the same filter), `coverage` (Σ group counter = matched), `comparison` (`aggregate` vs `mapreduce`, field by field; floats with `rel_tol 1e-9`), `executions[]` (`elapsed_ms`, `groups_returned`, `plan` = per-shard summary of `explain` with `executionStats`), `topology` (`$collStats {count: {}}` per shard).
- Limits: `maxTimeMS = 60000`; nginx allows 90 s on `/api/v1/distributed/`. `explain=true` executes the query a second time.








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
        for scope in ('kaggle-cs', 'synthetic-cs'):
            await self.db.corpus_counters.update_one({'_id':scope}, {'$setOnInsert':{'stored_documents':0}}, upsert=True)
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
        # One counter document per corpus scope; the total keeps its stage 9-12 meaning for kaggle-only stacks.
        counters = {row['_id']: row['stored_documents'] async for row in self.db.corpus_counters.find({}, max_time_ms=2000)}
        return {'stored_documents': sum(counters.values()), 'stored_by_scope': counters,
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
```

### content_service/worker.py — dispatch

```python
async def dispatch():
        while True:
            try:
                async for row in repository.db.outbox.find({'sent':False}).limit(100):
                    queue = row.get('queue', 'corpus.completed')
                    await broker.publish(queue, row['payload'])
                    if queue == SEARCH_INDEX_QUEUE:
                        # Index events carry document text; once confirmed by the broker they are not kept.
                        await repository.db.outbox.delete_one({'_id':row['_id']})
                    else:
                        await repository.db.outbox.update_one({'_id':row['_id']},{'$set':{'sent':True}})
            except Exception:
                logging.exception('Content outbox dispatch failed; retained for retry')
            await asyncio.sleep(.1)
```

### content_service/infrastructure/database/distributed_aggregation.py — build_match

```python
def build_match(query: DistributedAggregationQuery) -> dict:
    # `$in` over both scopes keeps the {corpus_scope, metadata.document_type, _id} index usable for "all".
    match = {"corpus_scope": {"$in": SCOPES} if query.corpus_scope == "all" else query.corpus_scope,
             "publication_status": "published", "metadata.template_version": "2"}
    if query.resolved_document_type:
        match["metadata.document_type"] = query.resolved_document_type
    return match
```

### content_service/infrastructure/database/distributed_aggregation.py — build_pipeline

```python
def build_pipeline(query: DistributedAggregationQuery) -> list[dict]:
    metric = query.metric
    pipeline: list[dict] = [{"$match": build_match(query)}]
    if metric == "map_pool":
        pipeline.append({"$group": {
            "_id": {"$ifNull": ["$metadata.map_name", None]}, "maps": {"$sum": 1},
            "scored": {"$sum": _if(SCORED, 1)}, "rounds": {"$sum": _if(SCORED, {"$add": [S1, S2]})},
            "margin": {"$sum": _if(SCORED, {"$abs": {"$subtract": [S1, S2]}})}, **WINS}})
    elif metric == "document_types":
        pipeline.append({"$group": {
            "_id": {"corpus_scope": "$corpus_scope", "document_type": {"$ifNull": ["$metadata.document_type", None]}},
            "documents": {"$sum": 1}, "with_players": {"$sum": _if({"$gt": [{"$size": PLAYERS}, 0]}, 1)},
            "player_rows": {"$sum": {"$size": PLAYERS}}, **WINS}})
    elif metric == "series_scores":
        score = {"$concat": [{"$toString": {"$toLong": {"$floor": {"$max": [S1, S2]}}}}, ":",
                             {"$toString": {"$toLong": {"$floor": {"$min": [S1, S2]}}}}]}
        pipeline.append({"$group": {
            "_id": {"best_of": {"$ifNull": ["$metadata.best_of", None]}, "score": _if(SCORED, score, None)},
            "documents": {"$sum": 1}, **WINS}})
    elif metric == "top_players":
        pipeline += [{"$unwind": "$metadata.players"},
                     {"$match": {"metadata.players.player_id": {"$ne": None}}},
                     {"$group": {"_id": "$metadata.players.player_id", "name": {"$max": "$metadata.players.name"},
                                 "documents": {"$sum": 1}, "kills": _player_stat("kills"),
                                 "deaths": _player_stat("deaths"), "assists": _player_stat("assists"),
                                 "adr_sum": _player_stat("adr"), "adr_n": {"$sum": _if({"$isNumber": "$metadata.players.adr"}, 1)},
                                 "kast_sum": _player_stat("kast"), "kast_n": {"$sum": _if({"$isNumber": "$metadata.players.kast"}, 1)}}}]
    pipeline.append(_sort_stage(metric))
    if metric == "top_players":
        pipeline.append({"$limit": query.limit})
    return pipeline
```

### content_service/infrastructure/database/distributed_aggregation.py — build_map_reduce

```python
def build_map_reduce(query: DistributedAggregationQuery) -> dict:
    return {"mapReduce": "source_documents", "map": Code(map_function(query.metric)),
            "reduce": Code(REDUCE_FUNCTION), "query": build_match(query), "out": {"inline": 1}}
```

### content_service/infrastructure/database/distributed_aggregation.py — count

```python
async def count(self, query: DistributedAggregationQuery) -> int:
        return await self.documents.count_documents(build_match(query), maxTimeMS=MAX_TIME_MS)
```

### content_service/infrastructure/database/distributed_aggregation.py — execute

```python
async def execute(self, query: DistributedAggregationQuery, engine: str) -> dict:
        if engine == "aggregate":
            pipeline = build_pipeline(query)
            command = {"aggregate": "source_documents", "pipeline": pipeline, "cursor": {}, "allowDiskUse": True}
            started = time.perf_counter()
            cursor = await self.documents.aggregate(pipeline, maxTimeMS=MAX_TIME_MS, allowDiskUse=True)
            raw = await cursor.to_list()
            elapsed = time.perf_counter() - started
            rows = [normalize(query.metric, doc["_id"], {k: v for k, v in doc.items() if k != "_id"}) for doc in raw]
        elif engine == "mapreduce":
            command = build_map_reduce(query)
            started = time.perf_counter()
            result = await self.db.command({**command, "maxTimeMS": MAX_TIME_MS})
            elapsed = time.perf_counter() - started
            raw = result["results"]
            rows = [normalize(query.metric, doc["_id"], doc["value"]) for doc in raw]
        else:
            raise ValueError("Unknown engine")
        rows = sort_rows(query.metric, rows)
        if query.metric == "top_players":
            rows = rows[:query.limit]
        plan = None
        if query.explain:
            explain = await self.db.command({"explain": command, "verbosity": "executionStats", "maxTimeMS": MAX_TIME_MS})
            plan = summarize_explain(explain)
        return {"engine": engine, "rows": rows, "elapsed_ms": round(elapsed * 1000, 1),
                "groups_returned": len(raw), "plan": plan}
```

### content_service/infrastructure/database/distributed_aggregation.py — topology

```python
async def topology(self) -> dict:
        cursor = await self.documents.aggregate([{"$collStats": {"count": {}}}], maxTimeMS=MAX_TIME_MS)
        stats = await cursor.to_list()
        return {"sharded": any("shard" in row for row in stats),
                "shards": sorted(({"shard": row.get("shard", "local"), "documents": _number(row.get("count", 0))}
                                  for row in stats), key=lambda row: row["shard"])}
```

## Elasticsearch queries (cs-sharded only)

Search owns alias `cs-documents` -> index `cs-documents-v1` (`INDEX_DEFINITION`: 1 shard, 0 replicas, `dynamic: strict`, analyzer `cs_text` = standard + lowercase + asciifolding; `metadata` kept in `_source` with `enabled: false`). Writes: one `POST /_bulk` per `search.index` event, `index` actions with `_id = document_id`, `version = document version`, `version_type = external_gte` (409 = stale, skipped). Reads: `POST /cs-documents/_search` built by `build_search_body` (scoring `multi_match` + non-scoring `filter`, map filter as `post_filter`, highlight with U+E000/U+E001 markers, facets, `timeout: 3s`, `track_total_hits`); `GET /_cluster/health`, `GET /cs-documents/_count` and a `size: 0` terms aggregation for `/search/status`. Modes: `all` = `cross_fields` AND, `any` = `best_fields` OR, `phrase` = `phrase`, `fuzzy` = `best_fields` AND with `fuzziness: AUTO:5,9` on name fields only. Backfill source (Content, MongoDB): `find(backfill_filter(scope)).sort(_id)` in `content_service/reindex.py`.

### search_service/infrastructure/search/elasticsearch_documents.py — text_query

```python
def text_query(query: FullTextQuery) -> dict:
    text = query.text
    if not text:
        return {'match_all': {}}
    if query.mode == 'phrase':
        return {'multi_match': {'query': text, 'type': 'phrase', 'fields': list(SEARCH_FIELDS)}}
    if query.mode == 'any':
        return {'multi_match': {'query': text, 'type': 'best_fields', 'operator': 'or', 'fields': list(SEARCH_FIELDS)}}
    if query.mode == 'fuzzy':
        return {'multi_match': {'query': text, 'type': 'best_fields', 'operator': 'and', 'fuzziness': 'AUTO:5,9',
                                'prefix_length': 1, 'max_expansions': 20, 'fields': list(FUZZY_FIELDS)}}
    # all: every word must match, but words may come from different fields (team + map + player).
    return {'multi_match': {'query': text, 'type': 'cross_fields', 'operator': 'and', 'fields': list(SEARCH_FIELDS)}}
```

### search_service/infrastructure/search/elasticsearch_documents.py — scope_filters

```python
def scope_filters(query: FullTextQuery) -> list[dict]:
    filters = []
    if query.corpus_scope != 'all':
        filters.append({'term': {'corpus_scope': query.corpus_scope}})
    if not query.include_synthetic:
        filters.append({'term': {'is_synthetic': False}})
    if query.document_type:
        filters.append({'term': {'document_type': query.document_type}})
    return filters
```

### search_service/infrastructure/search/elasticsearch_documents.py — build_search_body

```python
def build_search_body(query: FullTextQuery) -> dict:
    """Query DSL: scoring query + non-scoring filters; the map filter is a post_filter so the map facet
    still lists every map for the current text query (other facets apply it explicitly)."""
    map_filter = {'term': {'map_name': query.map_name}} if query.map_name else None
    within_map = {'filter': map_filter or {'match_all': {}}}
    body = {
        'query': {'bool': {'must': [text_query(query)], 'filter': scope_filters(query)}},
        'from': query.offset, 'size': query.page_size, 'track_total_hits': True, 'timeout': '3s',
        'sort': [{'_score': 'desc'}, {'played_at': {'order': 'desc', 'missing': '_last'}}, {'id': 'asc'}],
        'track_scores': True,
        '_source': {'excludes': ['metadata.players']},
        'highlight': {
            'pre_tags': [HIGHLIGHT_PRE], 'post_tags': [HIGHLIGHT_POST], 'encoder': 'default',
            'fields': {'title': {'number_of_fragments': 0}, 'team1': {'number_of_fragments': 0},
                       'team2': {'number_of_fragments': 0}, 'tournament': {'number_of_fragments': 0},
                       'map_name.text': {'number_of_fragments': 0},
                       'player_names': {'number_of_fragments': 5, 'fragment_size': 80},
                       'text': {'number_of_fragments': 3, 'fragment_size': 160}},
        },
        'aggs': {
            'map_name': {'terms': {'field': 'map_name', 'size': 30}},
            'corpus_scope': {**within_map, 'aggs': {'values': {'terms': {'field': 'corpus_scope'}}}},
            'document_type': {**within_map, 'aggs': {'values': {'terms': {'field': 'document_type'}}}},
            'is_synthetic': {**within_map, 'aggs': {'values': {'terms': {'field': 'is_synthetic'}}}},
        },
    }
    if map_filter:
        body['post_filter'] = map_filter
    return body
```

### search_service/infrastructure/search/elasticsearch_documents.py — bulk_payload

```python
def bulk_payload(documents: list[dict], index: str = ALIAS) -> str:
    lines = []
    for document in documents:
        lines.append(json.dumps({'index': {'_index': index, '_id': document['id'], 'version': document['version'],
                                           'version_type': 'external_gte'}}))
        lines.append(json.dumps(document, ensure_ascii=False))
    return '\n'.join(lines) + '\n'
```

### search_service/infrastructure/search/elasticsearch_documents.py — summarize_bulk

```python
def summarize_bulk(response: dict) -> dict:
    """409 version conflicts are stale events (a newer version is indexed): skipped, not failures."""
    indexed = stale = 0
    failures = []
    for item in response.get('items', []):
        result = item.get('index', {})
        status = result.get('status', 500)
        if status < 300:
            indexed += 1
        elif status == 409:
            stale += 1
        else:
            failures.append({'id': result.get('_id'), 'status': status, 'error': (result.get('error') or {}).get('type')})
    if failures:
        transient = any(f['status'] in (429, 503) or f['status'] >= 500 for f in failures)
        message = f'Bulk indexing failed for {len(failures)} documents: {failures[:3]}'
        raise SearchBackendUnavailable(message) if transient else ValueError(message)
    return {'indexed': indexed, 'stale': stale}
```

### content_service/reindex.py — backfill_filter

```python
def backfill_filter(scope: str) -> dict:
    if scope not in ('all', *SCOPES):
        raise ValueError('Unknown corpus scope')
    return {'publication_status': 'published', 'corpus_scope': {'$in': list(SCOPES)} if scope == 'all' else scope}
```

## PostgreSQL queries

DDL and constraints: `ingestion_service/infrastructure/database/migrations/001_replay.sql` (`replay_jobs`) and `002_partitioning.sql` (`replay_batches`, `replay_outbox`: `PARTITION BY RANGE (created_at)`, daily UTC partitions `<table>_pYYYYMMDD` plus a `DEFAULT` partition; keys `(id, created_at)`; composite FK `replay_outbox(id, created_at) -> replay_batches(id, created_at)`). Parameters are bound by asyncpg.

Partition DDL is issued by `ingestion_service/infrastructure/database/partitioning.py`; identifiers are built only from the fixed table names and dates. Creation: `CREATE TABLE <table>_pYYYYMMDD PARTITION OF <table> FOR VALUES FROM (day 00:00 UTC) TO (next day 00:00 UTC)`; rows stranded in `DEFAULT` are moved with `CREATE TABLE ... (LIKE ...)`, `INSERT ... SELECT`, `DELETE` and `ALTER TABLE ... ATTACH PARTITION`. Retention: `LOCK TABLE replay_batches, replay_outbox IN ACCESS EXCLUSIVE MODE` (with `lock_timeout`), `count(*)` of `NOT sent` / `status = 'pending'` rows in the expired partitions, then `DROP TABLE replay_outbox_pD`, `ALTER TABLE replay_batches DETACH PARTITION replay_batches_pD`, `DROP TABLE replay_batches_pD`.

### ingestion_service/infrastructure/database/replay_store.py:112

```sql
SELECT * FROM replay_jobs ORDER BY created_at DESC,id LIMIT $1 OFFSET $2
```

### ingestion_service/infrastructure/database/replay_store.py:109

```sql
SELECT * FROM replay_jobs WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:113

```sql
SELECT count(*) FROM replay_jobs
```

### ingestion_service/infrastructure/database/replay_store.py:58

```sql
SELECT pg_advisory_xact_lock($1)
```

### ingestion_service/infrastructure/database/replay_store.py:98

```sql
INSERT INTO replay_jobs
                  (id,idempotency_key,request_hash,snapshot_id,snapshot_hash,total,status,target_rate,validation_rejected)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT(idempotency_key) DO NOTHING
```

### ingestion_service/infrastructure/database/replay_store.py:103

```sql
SELECT * FROM replay_jobs WHERE idempotency_key=$1
```

### ingestion_service/infrastructure/database/replay_store.py:118

```sql
SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE
```

### ingestion_service/infrastructure/database/replay_store.py:126

```sql
UPDATE replay_jobs SET status=$2,target_rate=$3,next_at=now(),updated_at=now() WHERE id=$1 RETURNING *
```

### ingestion_service/infrastructure/database/replay_store.py:135

```sql
SELECT pg_advisory_xact_lock($1)
```

### ingestion_service/infrastructure/database/replay_store.py:156

```sql
SELECT * FROM replay_jobs WHERE status='running' AND produced<total
                    AND next_at<=now() AND produced-inserted-duplicates-rejected<1000
                    ORDER BY next_at LIMIT 1 FOR UPDATE SKIP LOCKED
```

### ingestion_service/infrastructure/database/replay_store.py:173

```sql
INSERT INTO replay_batches(id,job_id,start_offset,end_offset) VALUES($1,$2,$3,$4) RETURNING created_at
```

### ingestion_service/infrastructure/database/replay_store.py:175

```sql
INSERT INTO replay_outbox(id,payload,created_at) VALUES($1,$2::jsonb,$3)
```

### ingestion_service/infrastructure/database/replay_store.py:176

```sql
UPDATE replay_jobs SET produced=$2,next_at=$3,updated_at=now() WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:185

```sql
SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE
```

### ingestion_service/infrastructure/database/replay_store.py:189

```sql
SELECT * FROM replay_batches WHERE id=$1 AND job_id=$2 AND created_at>=$3 FOR UPDATE
```

### ingestion_service/infrastructure/database/replay_store.py:202

```sql
UPDATE replay_batches SET status='completed' WHERE id=$1 AND created_at=$2
```

### ingestion_service/infrastructure/database/replay_store.py:203

```sql
SELECT min(start_offset) FROM replay_batches WHERE job_id=$1 AND created_at>=$2 AND status!='completed'
```

### ingestion_service/infrastructure/database/replay_store.py:207

```sql
UPDATE replay_jobs SET inserted=inserted+$2,duplicates=duplicates+$3,rejected=rejected+$4,checkpoint=$5,status=$6,updated_at=now() WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:163

```sql
UPDATE replay_jobs SET status='failed',error='Snapshot changed',updated_at=now() WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:196

```sql
UPDATE replay_batches SET status='failed' WHERE id=$1 AND created_at=$2
```

### ingestion_service/infrastructure/database/replay_store.py:197

```sql
UPDATE replay_jobs SET status='failed',error=$2,updated_at=now() WHERE id=$1
```

### ingestion_service/worker.py:22

```sql
SELECT id,created_at,payload FROM replay_outbox WHERE NOT sent ORDER BY created_at LIMIT 50 FOR UPDATE SKIP LOCKED
```

### ingestion_service/worker.py:26

```sql
UPDATE replay_outbox SET sent=true WHERE id=$1 AND created_at=$2
```

### ingestion_service/presentation/api/app.py:56

```sql
SELECT 1
```

### ingestion_service/infrastructure/database/partitioning.py:100

```sql
SELECT c.relkind::text FROM pg_class c WHERE c.oid = to_regclass($1)
```

### ingestion_service/infrastructure/database/partitioning.py:145

```sql
INSERT INTO replay_outbox (id, payload, sent, created_at)
           SELECT id, payload, sent, created_at FROM replay_outbox_legacy
```

### ingestion_service/infrastructure/database/partitioning.py:175

```sql
SELECT to_regclass($1) IS NOT NULL
```

### ingestion_service/infrastructure/database/partitioning.py:224

```sql
SELECT parent.relname AS parent, child.relname AS name,
                  pg_get_expr(child.relpartbound, child.oid) AS bound,
                  pg_total_relation_size(child.oid) AS bytes
           FROM pg_inherits i
           JOIN pg_class parent ON parent.oid = i.inhparent
           JOIN pg_class child ON child.oid = i.inhrelid
           WHERE i.inhparent IN (to_regclass('replay_batches'), to_regclass('replay_outbox'))
           ORDER BY parent.relname, child.relname
```

### ingestion_service/infrastructure/database/partitioning.py:115

```sql
SELECT i.relname FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid
               WHERE x.indrelid = to_regclass($1)
```

### ingestion_service/infrastructure/database/partitioning.py:141

```sql
INSERT INTO replay_batches (id, job_id, start_offset, end_offset, status, created_at)
            SELECT b.id, b.job_id, b.start_offset, b.end_offset, b.status,
```

### ingestion_service/infrastructure/database/partitioning.py:148

```sql
SELECT count(*) FROM
```

### ingestion_service/infrastructure/database/partitioning.py:191

```sql
SELECT count(*) FROM
```

### ingestion_service/infrastructure/database/partitioning.py:199

```sql
SELECT * FROM
```

### ingestion_service/infrastructure/database/partitioning.py:202

```sql
DELETE FROM
```

### ingestion_service/infrastructure/database/partitioning.py:254

```sql
SELECT count(*) FROM
```

### ingestion_service/infrastructure/database/partitioning.py:256

```sql
SELECT count(*) FROM
```

### ingestion_service/infrastructure/database/partitioning.py:136

```sql
SELECT DISTINCT (
```

### ingestion_service/infrastructure/database/partitioning.py:241

```sql
SELECT count(*) AS rows, count(*) FILTER (WHERE NOT sent) AS unsent, min(created_at) AS min_created, max(created_at) AS max_created FROM
```

### ingestion_service/infrastructure/database/partitioning.py:244

```sql
SELECT count(*) AS rows, count(*) FILTER (WHERE status = 'pending') AS pending, min(created_at) AS min_created, max(created_at) AS max_created FROM
```

### ingestion_service/infrastructure/database/partitioning.py:275

```sql
SELECT pg_advisory_xact_lock($1)
```

### ingestion_service/infrastructure/database/partitioning.py:317

```sql
SELECT pg_advisory_xact_lock($1)
```

### ingestion_service/infrastructure/database/partitioning.py:321

```sql
SELECT count(*) FROM
```

### ingestion_service/infrastructure/database/partitioning.py:216

```sql
SELECT DISTINCT (created_at AT TIME ZONE 'UTC')::date AS day FROM
```

### ingestion_service/infrastructure/database/partitioning.py:283

```sql
SELECT pg_total_relation_size(to_regclass($1))
```

### ingestion_service/infrastructure/database/partitioning.py:285

```sql
SELECT count(*) FROM
```
## Outcomes and indexes

Batch completion returns `{job_id, batch_id, checkpoint, inserted, duplicates, rejected}`. The sum of counts must match the batch size. Failed batches carry `error` instead of successful counts. Job idempotency keys are unique. `replay_batches`/`replay_outbox` are partitioned, so their primary keys are `(id, created_at)`. `id = uuid5(job_id, start_offset)` stays globally unique by construction: `start_offset` is the job's `produced` value, advanced under the job row lock. `replay_batches(job_id,start_offset)` has a plain index. Pending batches/outbox entries have partial indexes, created on every partition. Completion lookups add `created_at >= job.created_at`, and outbox/batch updates use the full `(id, created_at)` key, so partitions are pruned. MongoDB has unique `_id`, filter indexes, a committed-time index and an outbox sent-state index.

## Manual reconciliation

```javascript
db.source_documents.countDocuments({corpus_scope:"kaggle-cs"})
db.corpus_counters.findOne({_id:"kaggle-cs"})
db.source_documents.countDocuments({corpus_scope:"synthetic-cs"})
db.corpus_counters.findOne({_id:"synthetic-cs"})
db.source_documents.countDocuments({corpus_scope:"synthetic-cs", is_synthetic:{$ne:true}})  // must be 0
db.committed_batches.find({}, {result:1}).limit(5)
```

Each document count must agree with the counter of its scope. The counter is updated transactionally; reconciliation is an acceptance check, not a one-second full scan.
