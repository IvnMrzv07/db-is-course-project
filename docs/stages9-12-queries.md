# Stages 9–12 query catalogue

## MongoDB queries

All queries target Content-owned collections, use sessions for batch writes and bounded execution for public reads. `_id` is a stable UUID string. The services issue no sharding or partitioning commands; in the optional sharded variant, sharding is configured by `deploy/mongo-sharded-init.sh`, not by Content. The only exception is the operator command `content_service.manage reset`, which drops and reshards the collection.

### Public reads and filters

`GET /documents?q=Alpha&document_type=map&page=1&page_size=20` returns `{items, total, page, page_size, degraded}`; `degraded: true` means a shard did not answer and the list is partial. `GET /documents/{id}` returns the full document or 404. Literal search is escaped before `$regex` with option `i`. Dates include the full end date. Exact team matching covers both team fields. Every list query is restricted to one `corpus_scope` (`kaggle-cs` by default; `&corpus_scope=synthetic-cs` selects the generated load corpus), so factual and synthetic documents are never mixed in one result. `GET /corpus/statistics` returns `stored_documents` (sum over scopes) and `stored_by_scope`.

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
```

### content_service/infrastructure/database/corpus_repository.py — browse

```python
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
```

### content_service/infrastructure/database/corpus_repository.py — _counters

```python
async def _counters(self):
        return counters_by_scope([row async for row in self.db.corpus_counters.find({}, max_time_ms=2000)])
```

### content_service/infrastructure/database/corpus_repository.py — _total

```python
async def _total(self, query, where):
        """Counting millions of load documents does not fit the read time limit: use counters or a bounded count."""
        if query.corpus_scope != LOAD_SCOPE:
            return await self.documents.count_documents(where, maxTimeMS=2000)
        if query.is_whole_scope:
            return (await self._counters()).get(LOAD_SCOPE, 0)
        return await self.documents.count_documents(where, limit=LOAD_COUNT_LIMIT, maxTimeMS=2000)
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
        # Slots are summed per corpus scope; the total keeps its stage 9-12 meaning for kaggle-only stacks.
        counters = await self._counters()
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
```

### content_service/infrastructure/database/corpus_repository.py — unsent

```python
async def unsent(self, limit):
        return [row async for row in self.db.outbox.find({'sent': False}).limit(limit)]
```

### content_service/infrastructure/database/corpus_repository.py — mark_sent

```python
async def mark_sent(self, rows):
        """Confirmed by the broker: completions are marked, index events (they carry document text) are removed."""
        finished = [row['_id'] for row in rows if row.get('queue') == SEARCH_INDEX_QUEUE]
        marked = [row['_id'] for row in rows if row.get('queue') != SEARCH_INDEX_QUEUE]
        if finished:
            await self.db.outbox.delete_many({'_id': {'$in': finished}})
        if marked:
            await self.db.outbox.update_many({'_id': {'$in': marked}},
                                             {'$set': {'sent': True, 'sent_at': datetime.now(timezone.utc)}})
```

### content_service/infrastructure/database/cluster_status.py — status

```python
async def status(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        hello = await self.client.admin.command('hello')
        if hello.get('msg') != 'isdbgrid':
            return {'topology': 'single', 'shards': [], 'available': bool(hello.get('isWritablePrimary')), 'sampled_at': now}
        shards = (await self.client.admin.command('listShards'))['shards']
        pools = (await self.client.admin.command('connPoolStats')).get('replicaSets', {})
        views = [shard_view(shard, pools) for shard in sorted(shards, key=lambda shard: shard['_id'])]
        primary = await self.client.config.databases.find_one({'_id': self.database}, {'primary': 1})
        available = all(view['available'] for view in views)
        counts = {}
        if available:  # $collStats needs every shard; during an outage only availability is reported
            try:
                cursor = await self.client[self.database].source_documents.aggregate(
                    [{'$collStats': {'count': {}}}], maxTimeMS=COUNT_TIMEOUT_MS)
                counts = {row['shard']: row['count'] async for row in cursor}
            except PyMongoError:
                pass
        for view in views:
            # Collection metadata: after an unclean stop (SIGKILL) WiredTiger reports too few documents until
            # `validate` runs, although nothing is lost. Never use it as proof; `content_service.manage verify` is.
            view['documents_estimate'] = counts.get(view['id'])
            # Receipts, counters and the outbox are unsharded: without this shard nothing can commit.
            view['database_primary'] = bool(primary) and primary['primary'] == view['id']
        return {'topology': 'sharded', 'shards': views, 'available': available, 'sampled_at': now}
```

### content_service/infrastructure/database/corpus_maintenance.py — verify

```python
async def verify(self, job: LoadJob, confirmed: int, produced: int) -> dict:
        """Look up every expected ID. Documents below `confirmed` must exist; up to `produced` they may be in flight."""
        if not 0 <= confirmed <= produced:
            raise ValueError('Expected 0 <= confirmed <= produced')
        limit, found, in_flight, missing = asyncio.Semaphore(PARALLEL), 0, 0, []

        async def check(start: int, end: int):
            nonlocal found, in_flight
            async with limit:
                identifiers = job.identifiers(start, end)
                present = {row['_id'] async for row in self.documents.find({'_id': {'$in': identifiers}}, {'_id': 1})}
            for offset, identifier in enumerate(identifiers, start):
                if identifier in present:
                    found, in_flight = found + (offset < confirmed), in_flight + (offset >= confirmed)
                elif offset < confirmed:
                    missing.append((offset, identifier))
        # One group of chunks at a time: millions of IDs are never in memory together.
        for group in range(0, produced, CHUNK * PARALLEL):
            await asyncio.gather(*(check(start, min(start + CHUNK, produced))
                                   for start in range(group, min(group + CHUNK * PARALLEL, produced), CHUNK)))
        missing.sort()
        unexpected = None
        if job.bounds:
            first, last = job.bounds
            unexpected = await self.documents.count_documents({'_id': {'$gte': first, '$lte': last}}) - found - in_flight
        return {'job_id': str(job.job_id), 'confirmed': confirmed, 'found': found, 'missing': len(missing),
                'missing_sample': [{'index': index, 'id': identifier} for index, identifier in missing[:SAMPLE]],
                'in_flight_found': in_flight, 'unexpected': unexpected, 'ok': not missing and not unexpected}
```

### content_service/infrastructure/database/corpus_maintenance.py — stats

```python
async def stats(self, *, exact: bool = True) -> dict:
        counters = counters_by_scope([row async for row in self.db.corpus_counters.find({})])
        shards = []
        async for row in await self.documents.aggregate([{'$collStats': {'storageStats': {}}}]):
            storage = row['storageStats']
            # `count` and `size` are metadata and stay too low after an unclean stop of a shard, until `validate`.
            shards.append({'shard': row.get('shard', 'single'), 'documents_estimate': storage['count'], 'data_bytes': storage['size'],
                           'storage_bytes': storage['storageSize'], 'index_bytes': storage['totalIndexSize'],
                           'reusable_bytes': storage.get('freeStorageSize', 0)})
        shards.sort(key=lambda row: row['shard'])
        return {'counters': counters, 'documents_exact': await self.documents.count_documents({}) if exact else None,
                'documents_estimate': sum(row['documents_estimate'] for row in shards), 'shards': shards,
                'receipts': await self.db.committed_batches.estimated_document_count(),
                'outbox': await self.db.outbox.estimated_document_count()}
```

### content_service/infrastructure/database/corpus_maintenance.py — _delete

```python
async def _delete(self, identifiers: list[str]) -> int:
        """Documents and their counter change in one transaction, so the dashboard total stays exact."""
        slot = counter_id(LOAD_SCOPE, str(uuid4()))

        async def transaction(session):
            result = await self.documents.delete_many({'_id': {'$in': identifiers}, 'corpus_scope': LOAD_SCOPE}, session=session)
            if result.deleted_count:
                await self.db.corpus_counters.update_one({'_id': slot}, {'$inc': {'stored_documents': -result.deleted_count}},
                                                         upsert=True, session=session)
            return result.deleted_count
        async with self.client.start_session() as session:
            return await session.with_transaction(transaction, read_concern=ReadConcern('snapshot'),
                                                  write_concern=WriteConcern('majority'))
```

### content_service/infrastructure/database/corpus_maintenance.py — _pages

```python
async def _pages(self, total: int):
        """Load document IDs in ID order (for ordered IDs: the oldest first)."""
        last, remaining = '', total
        while remaining > 0:
            rows = self.documents.find({'corpus_scope': LOAD_SCOPE, 'publication_status': 'published', '_id': {'$gt': last}},
                                       {'_id': 1}).sort('_id', 1).limit(min(CHUNK * PARALLEL, remaining))
            page = [row['_id'] async for row in rows]
            if not page:
                return
            last, remaining = page[-1], remaining - len(page)
            yield page
```

### content_service/infrastructure/database/corpus_maintenance.py — reset

```python
async def reset(self, *, lean_indexes: bool = False) -> dict:
        """Drop all corpus collections (disk space returns at once) and recreate them, sharded behind mongos."""
        before = await self.stats()
        for name in COLLECTIONS:
            await self.db.drop_collection(name)
        shards = 0
        if (await self.client.admin.command('hello')).get('msg') == 'isdbgrid':
            shards = len((await self.client.admin.command('listShards'))['shards'])
            await self.client.admin.command('enableSharding', self.name)
            await self.documents.create_index([('_id', 'hashed')])
            await self.client.admin.command({'shardCollection': f'{self.name}.source_documents', 'key': {'_id': 'hashed'},
                                             'numInitialChunks': CHUNKS_PER_SHARD * shards})
        await MongoCorpusRepository(self.db).initialize(lean_indexes=lean_indexes)
        return {'dropped_documents': before['documents_exact'], 'shards': shards, 'after': await self.stats()}
```

### content_service/worker.py — dispatch_once

```python
async def dispatch_once(repository, publish, limit=DISPATCH_BATCH) -> int:
    """Publish unsent rows concurrently; rows without a broker confirm stay unsent for the next cycle."""
    rows = await repository.unsent(limit)
    outcomes = await asyncio.gather(*(publish(row.get('queue', 'corpus.completed'), row['payload']) for row in rows),
                                    return_exceptions=True)
    confirmed = [row for row, outcome in zip(rows, outcomes) if not isinstance(outcome, BaseException)]
    if confirmed:
        await repository.mark_sent(confirmed)
    failures = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
    if failures:
        raise failures[0]
    return len(confirmed)
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

DDL and constraints: `ingestion_service/infrastructure/database/migrations/001_replay.sql` (`replay_jobs`) and `003_high_load.sql` (rate and status constraints), `002_partitioning.sql` (`replay_batches`, `replay_outbox`: `PARTITION BY RANGE (created_at)`, daily UTC partitions `<table>_pYYYYMMDD` plus a `DEFAULT` partition; keys `(id, created_at)`; composite FK `replay_outbox(id, created_at) -> replay_batches(id, created_at)`). Parameters are bound by asyncpg.

Partition DDL is issued by `ingestion_service/infrastructure/database/partitioning.py`; identifiers are built only from the fixed table names and dates. Creation: `CREATE TABLE <table>_pYYYYMMDD PARTITION OF <table> FOR VALUES FROM (day 00:00 UTC) TO (next day 00:00 UTC)`; rows stranded in `DEFAULT` are moved with `CREATE TABLE ... (LIKE ...)`, `INSERT ... SELECT`, `DELETE` and `ALTER TABLE ... ATTACH PARTITION`. Retention: `LOCK TABLE replay_batches, replay_outbox IN ACCESS EXCLUSIVE MODE` (with `lock_timeout`), `count(*)` of `NOT sent` / `status = 'pending'` rows in the expired partitions, then `DROP TABLE replay_outbox_pD`, `ALTER TABLE replay_batches DETACH PARTITION replay_batches_pD`, `DROP TABLE replay_batches_pD`.

### ingestion_service/infrastructure/database/replay_store.py:193

```sql
Delete the whole replay history; refused while a job could still produce or publish.
```

### ingestion_service/infrastructure/database/replay_store.py:158

```sql
SELECT * FROM replay_jobs ORDER BY created_at DESC,id LIMIT $1 OFFSET $2
```

### ingestion_service/infrastructure/database/replay_store.py:155

```sql
SELECT * FROM replay_jobs WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:159

```sql
SELECT count(*) FROM replay_jobs
```

### ingestion_service/infrastructure/database/replay_store.py:102

```sql
SELECT pg_advisory_xact_lock($1)
```

### ingestion_service/infrastructure/database/replay_store.py:144

```sql
INSERT INTO replay_jobs
                  (id,idempotency_key,request_hash,snapshot_id,snapshot_hash,total,status,target_rate,validation_rejected)
                  VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT(idempotency_key) DO NOTHING
```

### ingestion_service/infrastructure/database/replay_store.py:149

```sql
SELECT * FROM replay_jobs WHERE idempotency_key=$1
```

### ingestion_service/infrastructure/database/replay_store.py:164

```sql
SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE
```

### ingestion_service/infrastructure/database/replay_store.py:172

```sql
UPDATE replay_jobs SET status=$2,target_rate=$3,next_at=now(),updated_at=now() WHERE id=$1 RETURNING *
```

### ingestion_service/infrastructure/database/replay_store.py:180

```sql
SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE
```

### ingestion_service/infrastructure/database/replay_store.py:185

```sql
UPDATE replay_outbox SET sent=true WHERE NOT sent AND created_at>=$2
                    AND id IN (SELECT id FROM replay_batches WHERE job_id=$1 AND created_at>=$2 AND status='pending') RETURNING id,created_at
```

### ingestion_service/infrastructure/database/replay_store.py:188

```sql
UPDATE replay_batches SET status='cancelled' WHERE id=$1 AND created_at=$2
```

### ingestion_service/infrastructure/database/replay_store.py:197

```sql
SELECT count(*) FROM replay_jobs WHERE status IN ('running','paused')
```

### ingestion_service/infrastructure/database/replay_store.py:200

```sql
SELECT count(*) FROM replay_jobs
```

### ingestion_service/infrastructure/database/replay_store.py:209

```sql
SELECT pg_advisory_xact_lock($1)
```

### ingestion_service/infrastructure/database/replay_store.py:230

```sql
SELECT * FROM replay_jobs WHERE status='running' AND produced<total
                    AND next_at<=now() AND produced-inserted-duplicates-rejected<$1
                    ORDER BY next_at LIMIT 1 FOR UPDATE SKIP LOCKED
```

### ingestion_service/infrastructure/database/replay_store.py:247

```sql
INSERT INTO replay_batches(id,job_id,start_offset,end_offset) VALUES($1,$2,$3,$4) RETURNING created_at
```

### ingestion_service/infrastructure/database/replay_store.py:249

```sql
INSERT INTO replay_outbox(id,payload,created_at) VALUES($1,$2::jsonb,$3)
```

### ingestion_service/infrastructure/database/replay_store.py:250

```sql
UPDATE replay_jobs SET produced=$2,next_at=$3,updated_at=now() WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:277

```sql
SELECT id,created_at,payload FROM replay_outbox WHERE NOT sent ORDER BY created_at LIMIT $1 FOR UPDATE SKIP LOCKED
```

### ingestion_service/infrastructure/database/replay_store.py:297

```sql
SELECT * FROM replay_jobs WHERE id=$1 FOR UPDATE
```

### ingestion_service/infrastructure/database/replay_store.py:301

```sql
SELECT * FROM replay_batches WHERE id=$1 AND job_id=$2 AND created_at>=$3 FOR UPDATE
```

### ingestion_service/infrastructure/database/replay_store.py:314

```sql
UPDATE replay_batches SET status='completed' WHERE id=$1 AND created_at=$2
```

### ingestion_service/infrastructure/database/replay_store.py:315

```sql
SELECT min(start_offset) FROM replay_batches WHERE job_id=$1 AND created_at>=$2 AND status!='completed'
```

### ingestion_service/infrastructure/database/replay_store.py:319

```sql
UPDATE replay_jobs SET inserted=inserted+$2,duplicates=duplicates+$3,rejected=rejected+$4,checkpoint=$5,status=$6,updated_at=now() WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:190

```sql
UPDATE replay_jobs SET status='cancelled',updated_at=now() WHERE id=$1 RETURNING *
```

### ingestion_service/infrastructure/database/replay_store.py:236

```sql
UPDATE replay_jobs SET status='failed',error='Snapshot changed',updated_at=now() WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:290

```sql
UPDATE replay_outbox SET sent=true WHERE id=$1 AND created_at=$2
```

### ingestion_service/infrastructure/database/replay_store.py:308

```sql
UPDATE replay_batches SET status='failed' WHERE id=$1 AND created_at=$2
```

### ingestion_service/infrastructure/database/replay_store.py:309

```sql
UPDATE replay_jobs SET status='failed',error=$2,updated_at=now() WHERE id=$1
```

### ingestion_service/infrastructure/database/replay_store.py:285

```sql
UPDATE replay_jobs SET status='failed',error='Snapshot changed',updated_at=now() WHERE id=$1 AND status IN ('running','paused')
```

### ingestion_service/infrastructure/database/replay_store.py:286

```sql
UPDATE replay_batches SET status='failed' WHERE id=$1 AND created_at=$2
```

### ingestion_service/presentation/api/app.py:63

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

Batch completion returns `{job_id, batch_id, checkpoint, inserted, duplicates, rejected}`. The sum of counts must match the batch size. Failed batches carry `error` instead of successful counts. Job idempotency keys are unique. `replay_batches`/`replay_outbox` are partitioned, so their primary keys are `(id, created_at)`. `id = uuid5(job_id, start_offset)` stays globally unique by construction: `start_offset` is the job's `produced` value, advanced under the job row lock. `replay_batches(job_id,start_offset)` has a plain index. Unfinished batches (`status <> 'completed'`, the predicate of the checkpoint query) and unsent outbox entries have partial indexes, created on every partition; outbox payloads are references `{snapshot_id, snapshot_hash, start, end}`, not documents. Completion lookups add `created_at >= job.created_at`, and outbox/batch updates use the full `(id, created_at)` key, so partitions are pruned. MongoDB has unique `_id`, filter indexes, a committed-time index, an outbox sent-state index and a TTL index on `outbox.sent_at` (one day). Counters are kept in 64 slots per scope (`<scope>#NN`) plus the scope document; the stored total is their sum.

## Manual reconciliation

```javascript
db.source_documents.countDocuments({corpus_scope:"kaggle-cs"})
db.corpus_counters.aggregate([{$group:{_id:{$first:{$split:["$_id","#"]}},stored:{$sum:"$stored_documents"}}}])
db.source_documents.countDocuments({corpus_scope:"synthetic-cs"})
db.source_documents.countDocuments({corpus_scope:"synthetic-cs", is_synthetic:{$ne:true}})  // must be 0
db.committed_batches.find({}, {result:1}).limit(5)
```

Each document count must agree with the counter of its scope. The counter is updated transactionally; reconciliation is an acceptance check, not a one-second full scan.
