# Stages 9–12 runtime

## Ownership and boundaries

Content owns `source_documents`, `committed_batches`, `corpus_counters` and `outbox` in MongoDB `content`. Ingestion owns `replay_jobs`, `replay_batches` and `replay_outbox` in its PostgreSQL database. No service reads another service's database. RabbitMQ transports version-1 JSON batches and completions. Nginx routes `/api/v1/replays` and `/api/v1/snapshots` to Ingestion; other API paths go to Content.

The current modules diagram is `docs/diagrams/modules.mmd`. `docs/diagrams/target-modules.mmd` describes future services, sharding and search/cache components, not deployed services.

## Corpus identity and meaning

Only `cs2_all_tiers_games.csv` is read from the bundled ZIP. Stable UUIDv5 IDs use a source-scoped key: `match_id:series` or `match_id:map:game_id`. English templates report recorded facts and preserve missing values. Series rows and map rows are different document types, never independent observations to be summed for statistics. Team strings are source labels, not verified organization identities. Source timestamps have no declared timezone and are preserved without inventing one.

The immutable snapshot's CSV SHA-256 and template version are stored per document. A JSONL SHA-256 protects prepared input. A different snapshot/template for an existing ID is rejected pending an explicit migration. There is no public edit/delete API for this archival slice. `retrieved_at` records the local replay start; `stored_at` records ingestion into MongoDB. `is_synthetic=false` means factual descriptions from source rows, not invented matches.

### Template version 2 metadata

Template `"2"` keeps the v1 `title`, `text`, IDs and every v1 metadata key unchanged (string values), and adds JSON-typed structured fields for aggregation and filtering. `null` means the source did not record the value; nothing is imputed.

| Field | Type | Present on | Source / rule |
|---|---|---|---|
| `team1_id`, `team2_id` | string \| null | all | `team1_id`, `team2_id` (source team IDs) |
| `best_of` | int \| null | all | `bestOf` (`"3.0"` and `"3"` both → 3) |
| `score1`, `score2` | int \| null | all | series: `score1_match`/`score2_match`; map: `score1_game`/`score2_game` (rounds) |
| `winner` | `"team1"` \| `"team2"` \| `"draw"` \| null | all | derived from `score1`/`score2` only |
| `winner_team` | string \| null | all | team label of `winner` |
| `players` | list | all | one object per named player slot: `team` (1/2), `slot` (1–5), `player_id`, `name`, `kills`, `deaths`, `assists`, `kddiff` (int), `adr`, `kast` (float) |
| `map_name`, `map_id` | string \| null | map only | `map_name`, `map_id` |
| `games_played` | int \| null | series only | `games_played` |

The source `team1_win` flag is not used: it contradicts the series score in roughly half of the series rows (and in 170 map rows). Series rows sometimes carry one map's `map_name`/`score*_game`; these are ignored for series documents. Series player statistics are series totals and map player statistics are per-map values — the two must not be summed together. Expected preparation result is unchanged: 20,675 documents, 1 rejected row (line 20100).

Because `template_version` is part of the per-ID consistency check, replaying a v2 snapshot into a MongoDB that already holds v1 documents is rejected (`migration required`) until an explicit migration is performed.

## Synthetic load corpus (`synthetic-cs`)

Decision D38 and report section 2.2 allow synthetic texts only as a separate, clearly marked load corpus. `synthetic-cs` is a second immutable snapshot next to `kaggle-cs`; the factual corpus, its IDs and its preparation result are unchanged.

- **Generation (offline):** `python -m ingestion_service.infrastructure.datasets.synthesize_corpus` (venv from `requirements-synthetic.txt`; SDV 2.2.0 and CPU torch, never imported by the services). Two SDV `TVAESynthesizer` models (300 epochs, seed 2026, CPU, about 13 min in total) are trained on a **series table** (tournament, teams, best_of, scores, date, map-detail flag) and a winner/loser-oriented **map table** (map, round score, 10 players' kills/deaths/assists/ADR/KAST). `CTGANSynthesizer` can be selected with `--series-model/--map-model`. A 300-epoch CTGAN comparison was stopped after more than 80 minutes without a result, so TVAE is used.
- **Relations are built, not learned:** each series gets `score1+score2` map rows. Map winners follow the series score (the series winner takes the last map). Map names are unique within a series. Series player stats are the sum of the map stats, with ADR/KAST weighted by rounds. Rosters are fixed per team within a series. IDs: `match_id = S000001…`, `game_id = <match_id>-M<k>`.
- **Domain constraints (rejection sampling):**
  - series: non-negative integer scores; winner score = `(best_of+1)/2`; team1 ≠ team2; date within the real range;
  - maps: CS2 MR12 round score (13:0–11 or overtime 13+3k with a 2–4 round margin); non-negative integer counts; deaths ≤ rounds; KAST ≤ 100; values within the observed min/max; team kills vs. opponent deaths within the real 99th percentile (4).
- **Pseudonyms:** teams, tournaments and players become frequency-ranked `Synthetic Team NNN`, `Synthetic Tournament NNN` and `Synthetic Player NNN-k`. No real names are emitted. Every text starts with "Synthetic load-test record generated with SDV; it does not describe a real match."
- **Identity:** provider `sdv_synthetic_counter_strike` gives a different UUIDv5 namespace key from kaggle-cs. `prepare_corpus` also aborts if any synthetic ID collides with a factual ID, and rejects rows not marked `is_synthetic=True`. Documents carry `corpus_scope="synthetic-cs"`, `is_synthetic=true` and `metadata.generated_from_dataset="false"`.
- **Runtime:** Ingestion lists both snapshots (`/snapshots` exposes `is_synthetic`) and reads prepared JSONL lazily by line offsets (about 250 MB for synthetic-cs). Content accepts only the known scopes and rejects a scope/flag mismatch. Counters are kept per scope (`corpus_counters`, `stored_by_scope` in `/corpus/statistics`). `/documents` filters by `corpus_scope` (default `kaggle-cs`), so synthetic documents never mix into factual browsing or statistics.
- **Expected result:** kaggle-cs 20,675 + synthetic-cs 79,325 (36,088 series and 43,237 map documents, 0 rejected) = **100,000** documents. Quality evidence: `data/synthetic/synthetic-cs.quality.json` and `docs/coursework/stages/synthetic-data-summary/`.

## Sharded MongoDB variant (`deploy/docker-compose.sharded.yml`)

An optional, separate Compose project `cs-sharded` runs the same stack with MongoDB as a sharded cluster. It has its own volumes and its UI is on port 8082. The default `docker-compose.yml` stack still uses the single-member `rs0`.

- **Topology:**
  - config server replica set `cfgRS` (`cfg1:27019`);
  - three shards `shard1RS`/`shard2RS`/`shard3RS` (`shardN:27018`), each a single-member replica set;
  - one `mongos` router. Content's `MONGO_URL` is `mongodb://mongos:27017/`.
- **Initialisation:** `deploy/mongo-sharded-init.sh`, idempotent. It initiates the replica sets, runs `sh.addShard` ×3 and sets `chunksize` (`CHUNK_SIZE_MB`, default 128 MB; the 19 November evidence used 2 MB). It then runs `sh.enableSharding("content")`, creates `{_id: "hashed"}` and calls `shardCollection("content.source_documents", {_id: "hashed"}, numInitialChunks: 12)` on the empty collection. This pre-splits 4 chunks per shard before any insert. MongoDB 7.0's AutoMerger later merges adjacent chunks on the same shard (observed: 1 chunk per shard after the full load); document placement does not change.
- **Unsharded collections:** `committed_batches`, `corpus_counters` and `outbox` stay unsharded on the database's primary shard.
- **Unchanged code:** the Content code is unchanged. Each batch transaction becomes a distributed (multi-shard) transaction through `mongos`, with the same snapshot read concern and majority write concern. Upserts filter on `_id`, which is the shard key.
- **Query routing:** lookups by `_id` (`/documents/{uuid}`, the per-document consistency check) target one shard. `/documents` lists and filters by `corpus_scope`/`metadata.*` are scatter-gather across all shards: each shard uses its local compound index and `mongos` merge-sorts by `_id`.
- **Verified result (19 Nov):**
  - documents: 100,000 (kaggle-cs 20,675 + synthetic-cs 79,325, template `"2"`); counters match;
  - distribution: 33,457 / 33,123 / 33,420 documents and 4 / 4 / 4 chunks per shard;
  - observed throughput: about 200 documents/s.

  Evidence: `docs/coursework/stages/sharding-summary/`; collector: `tools/sharding/collect_evidence.js`.
- **Not resilient:** single-member replica sets on one host demonstrate data distribution, not fault tolerance.
- **Distributed map-reduce:** `GET /api/v1/distributed/map-reduce` (UI tab «Розподілені запити», `#distributed`) aggregates the v2 corpus on all shards through `mongos` using an aggregation pipeline and/or the `mapReduce` command, and returns per-shard `explain` metrics plus an engine comparison and a coverage check. It is read-only and works on the default unsharded stack too (`topology: "single"`, no merger part). Query details: `docs/stages9-12-queries.md`.
  - Verified on 100,000 documents (19 Nov): results of both engines are identical for all metrics; Σ of group counters = `countDocuments`; each shard runs `$match` + partial `$group` over its own index range (≈ 1/3 of the documents) and one shard merges (`mergeType: anyShard`).
  - Median server time: `aggregate` 0.16–1.5 s, `mapReduce` 0.74–5.6 s (JavaScript per document). Evidence: `docs/coursework/stages/map-reduce-summary/`; collector: `tools/sharding/collect_map_reduce_evidence.py`.

## Partitioned Ingestion outbox (`replay_batches`, `replay_outbox`)

Both tables are declaratively partitioned with `PARTITION BY RANGE (created_at)`. DDL is in `migrations/002_partitioning.sql`; the logic is in `ingestion_service/infrastructure/database/partitioning.py`. `replay_jobs` is not partitioned. It is small and long-lived.

- **Layout:** one partition per UTC day, `<table>_pYYYYMMDD` covering `[day 00:00 UTC, next day 00:00 UTC)`, plus `<table>_default`.
- **Keys:** PostgreSQL requires the partition key in every PK/UNIQUE constraint, so the keys are `(id, created_at)`. `replay_batches.created_at` is new. A batch and its outbox row are inserted in one transaction with the same `created_at`, and the composite FK `replay_outbox(id, created_at) → replay_batches(id, created_at)` keeps them in partitions with the same bounds. `id = uuid5(job_id, start_offset)` stays unique by construction, because `start_offset` is advanced under the job row lock. The former `UNIQUE(job_id, start_offset)` is now a plain index.
- **Creation:**
  - Every service start migrates the schema under advisory lock 912001 and creates partitions for today and the next `REPLAY_PARTITION_AHEAD_DAYS` days (default 1).
  - `produce()` re-checks this when the UTC date changes, so a write happens with today's partition in place.
  - If creation fails, the row goes to `DEFAULT` and the write still succeeds. The next maintenance cycle creates partitions for every day found in `DEFAULT` and moves those rows into them (`LIKE` copy → delete from default → `ATTACH PARTITION`). PostgreSQL would otherwise reject `CREATE ... PARTITION OF` for that range.
- **Migration of existing data:** a database with the old heap tables is converted in place on first start, in one transaction:
  1. the old tables and their indexes are renamed to `*_legacy`;
  2. partitions are created for every day present in the data;
  3. the rows are copied, with batch `created_at` taken from the outbox row, or from the job when there is no outbox row;
  4. the counts are verified;
  5. the legacy tables are dropped.

  A count mismatch rolls the whole migration back.
- **Retention:**
  - The ingestion worker runs a maintenance cycle every `REPLAY_PARTITION_MAINTENANCE_SECONDS` (default 3600). It first creates partitions, then handles day pairs whose end lies more than `REPLAY_PARTITION_RETENTION_DAYS` (default 7) in the past.
  - A day is dropped only when its outbox partition has **no `sent = false` rows** and its batch partition has **no `pending` batches**, so a late completion can still find its batch. Otherwise the day is logged as `skipped` (WARNING) and retried next cycle.
  - Each day runs in its own short transaction: advisory lock 912002, `LOCK TABLE replay_batches, replay_outbox IN ACCESS EXCLUSIVE MODE` with `lock_timeout` (`REPLAY_PARTITION_LOCK_TIMEOUT_MS`, default 5000), recheck, `DROP TABLE` of the outbox partition, `DETACH PARTITION` of the batch partition, then `DROP TABLE`. PostgreSQL refuses to drop a partition referenced by the FK directly.
  - `DEFAULT` partitions are never dropped. Rows left in them are reported as a warning.
- **Query pruning:**
  - the dispatcher updates `sent` by `(id, created_at)`, which touches one partition;
  - completion adds `created_at >= job.created_at` to the batch lookup and checkpoint query;
  - the pending-outbox scan is a `Merge Append` over the per-partition partial indexes.
- **Operator CLI** (inside the ingestion container):

  ```sh
  python -m ingestion_service.infrastructure.database.partitioning --report
  python -m ingestion_service.infrastructure.database.partitioning --cleanup [--retention-days N]
  python -m ingestion_service.infrastructure.database.partitioning --cleanup --dry-run --now <ISO time>   # simulated clock, dry run only
  ```
- **Evidence (19 Nov, `cs-sharded`):** `docs/coursework/stages/partitioning-summary/`.

## Full-text search (Elasticsearch, `cs-sharded` only)

- **Services:** `elasticsearch` (8.15.3, single node, `ES_JAVA_OPTS=-Xms512m -Xmx512m`, `mem_limit 1536m`, xpack security/TLS off, volume `es_data`), `search_worker` (indexer) and `search_api` (`/api/v1/search`, `/api/v1/search/status`; Nginx `location /api/v1/search`, upstream resolved per request).
- **Event:** with `SEARCH_INDEX_EVENTS=1` (set only in the sharded Compose file) `persist_batch` also inserts `outbox{_id: "index:<batch_id>", queue: "search.index", payload}` in the same transaction as the batch. The payload is `contracts.IndexSourceDocuments` (`event_type: source_documents.indexable`, schema 1): a projection (id, version, title, text, language, corpus_scope, is_synthetic, source_id, metadata) of every published document of the batch, duplicates included. The dispatcher publishes by `row.queue` and deletes index rows after the broker confirm (completion rows are still marked `sent`). A redelivered batch returns its receipt and stages no second event. Without the flag Content behaves exactly as before.
- **Indexing:** `search_worker` validates the whole event (domain `index_projection.project`: UUID, positive version, scope ↔ `is_synthetic`, document type) and issues one `_bulk` to alias `cs-documents` (index `cs-documents-v1`) with `_id = document_id`, `version = document version`, `version_type = external_gte`. Redelivery, replay and backfill are therefore idempotent; an older version gets 409 and is counted as `stale`. ES unavailable → nack+requeue with back-off, attempt counter unchanged (no quarantine during an outage); invalid events → retried, then `search.index.failed` after 5 attempts.
- **Backfill:** `python -m content_service.reindex [--scope all|kaggle-cs|synthetic-cs]` streams Content's own collection in `_id` order and publishes events of 100 documents (`origin: backfill`). Search never reads MongoDB. `python -m search_service.manage ensure|recreate|status [--wait-count N]` maintains the index.
- **Query states:** 200 `status: found|empty` (+`degraded: true` if ES timed out/shards failed), 422 invalid parameters, 503 `status: degraded` when ES is unreachable or the index is missing, 500 `status: error`. The UI shows degraded state and falls back to the literal Content search (`/documents`, one corpus, unranked).
- **Verified (19 Nov):** 100,000 documents indexed (kaggle-cs 20,675 + synthetic-cs 79,325) from 1,000 backfill events in 73.8 s (≈1,355 docs/s), 0 failures; a repeated backfill left 100,000 documents at external version 1; a kaggle-cs replay restored 5 documents deleted from ES through 207 `origin=store` events; warm queries 6–44 ms in ES (fuzzy 193 ms). Evidence: `docs/coursework/stages/search-summary/`; collector: `tools/search/collect_search_evidence.py`.

## High-load writing

- **Batch transaction:** one receipt lookup, one `find {_id: {$in}}`, one `insert_many` of new documents, one counter increment (slot `<scope>#NN` chosen by the batch ID), receipt and outbox row; snapshot read concern, majority write concern. Up to 1,000 documents per batch (`REPLAY_BATCH_SIZE`, default 500), `CONTENT_CONCURRENCY` (default 4) transactions per consumer. The same ID twice in a batch counts as a duplicate.
- **Worker roles:** `CONTENT_ROLES=consume|dispatch` (default both). On `cs-sharded` `content_worker` only consumes and can be scaled; exactly one `content_dispatcher` publishes the outbox. Sent rows expire after a day (TTL on `sent_at`).
- **Load source:** `prepare_corpus` writes `load-cs.base.jsonl` (4,000 rows of the synthetic snapshot). Snapshots `load-cs` (ordered IDs) and `load-cs-random` generate documents from it on the fly; `LOAD_DOCUMENTS` (default 20 million) is the size of one job. Generated texts are marked synthetic like `synthetic-cs`.
- **Reads:** lists of `load-cs` take their total from the counters (unfiltered) or count at most 10,000 matches.
- **Outage of a shard:** a commit attempt is limited to 20 s on the driver side, because `with_transaction` otherwise retries for 120 s. `StoreUnavailable` (connection errors, missing primary, timeouts, transient transaction errors) requeues the batch after a pause of 1–5 s. Every batch spans all shards, so writing stops until the shard returns; nothing is lost and no job fails. `/documents` answers with the remaining shards (`degraded: true`), `/cluster/status` shows each shard. If the missing shard is the database's primary shard, statistics are unavailable too.
- **Counts after SIGKILL:** `$collStats` and `estimatedDocumentCount` read WiredTiger metadata that is too low after an unclean stop until `validate` runs. `content_service.manage verify` and `countDocuments` are exact; `documents_estimate` fields are not proof.
- **Index profile:** `reset --lean-indexes` recreates the team, tournament and date indexes as partial indexes without `load-cs`. Services keep whichever profile the store was created with.

Operator commands (`python tools/ops/cs_ops.py --help`; they call `content_service.manage`, `ingestion_service.manage` and `search_service.manage` inside the containers):

| Command | Effect |
|---|---|
| `--shards 1\|3 up`, `stop` | one- or three-shard stand from the same Compose file (`cs-single` / `cs-sharded`, separate volumes) |
| `start [--snapshot load-cs] [--rate 0]`, `pause`, `resume`, `cancel --job` | replay jobs; cancelling drops staged but unpublished batches |
| `shard stop\|kill\|start N` | outage demonstration |
| `verify --job` | recomputes every confirmed ID and reports missing and unexpected documents; exit code 1 on a loss |
| `purge [--percent P \| --limit N \| --job ID] [--dry-run] --yes [--compact]` | deletes generated documents together with their counters; `compact` returns the space to the OS |
| `reset [--lean-indexes] --yes` | cancels jobs, stops workers, purges queues, recreates MongoDB collections (sharded), clears replay tables and the search index, restarts workers; import the factual snapshots again afterwards |

Measurements: `tools/load/README.md`.

## Transaction and recovery rules

PostgreSQL atomically stores each job's produced offset, batch identity and outbox reference (the dispatcher rebuilds the documents from the immutable input when it publishes). Workers claim jobs with row locks and `SKIP LOCKED`. Prepared input is verified on startup. Each job has a persistent next-production time; rate updates and pause/resume are committed immediately. Each job is limited to `REPLAY_MAX_OUTSTANDING` (default 20,000) outstanding documents. Actual throughput is measured separately from the requested rate.

MongoDB uses a session transaction with majority write concern for documents, unique batch receipt, counter and completion outbox. A repeated batch returns its original result; a new replay of the same documents reports duplicates. Publisher confirms precede the sent marker; consumer ACK follows persistence. A crash between these actions causes safe redelivery. PostgreSQL completion handling locks the job, counts a batch once, and advances its checkpoint only through contiguous completed batches.

A batch that cannot be committed because the store is unavailable is requeued without spending an attempt (see *High-load writing*). After five handler attempts with any other error a message goes to `<queue>.failed`. A failed Content batch also sends a failure completion, marking its job failed. Fix the cause and start a new replay; stable IDs preserve existing documents. Completion messages in `corpus.completed.failed` must be inspected and redriven with `python -m ingestion_service.infrastructure.messaging.redrive corpus.completed` in the worker container. The redrive utility only moves a bounded number of messages, uses confirms, and resets the retry count. Failed jobs are not silently reported complete. Queue backlog includes in-flight/outbox documents, not just RabbitMQ ready messages.

MongoDB and PostgreSQL outboxes are service-owned collections/tables, not direct cross-service queries. Search events (`search.index`) are published only when `SEARCH_INDEX_EVENTS=1` (the `cs-sharded` stand, see the full-text search section); the default stack publishes none and runs no indexer or cache consumer.

## API

Public GET endpoints: `/documents`, `/documents/{uuid}`, `/corpus/statistics`, `/cluster/status`, `/distributed/map-reduce` (60 s execution limit, see the sharded section); on `cs-sharded` also `/search` and `/search/status` (Search service, see the full-text search section). Document lists accept `q` (literal substring, max 200), `document_type=series|map`, exact `team`/`tournament`, inclusive `date_from`/`date_to`, `page` and `page_size` (default 20, max 100). Results sort by stable ID. MongoDB reads have a two-second execution limit. This is a bounded scan for substring matching, not a relevance engine.

Operator endpoints require `Authorization: Bearer <token>`: GET `/snapshots`; GET/POST `/replays`; GET `/replays/{uuid}`; PATCH `/replays/{uuid}/rate`; POST `/replays/{uuid}/pause`, `/resume` and `/cancel`. Rates are 10–100,000 documents/s or `0` (MAX, no pacing). Starting requires `Idempotency-Key` and returns 202. The same key with changed parameters returns 409. Unknown prepared input and invalid values return 422; missing records 404; unavailable databases 503. Live API documentation is available on each service's `/docs` when accessed directly on the internal network.

The UI keeps the operator token only in component memory. Changing away from the import page logs out. Sources are selected from a server allowlist; no arbitrary filesystem paths are accepted.

## Counters and logging

The persistent MongoDB counter changes in the document transaction. The dashboard samples it and sums inserted counts from indexed committed-batch records for a trailing ten-second rate. Duplicates do not raise that counter. Reconcile the counter against `source_documents.countDocuments` during acceptance, rather than scanning the corpus every second.

Attempted/produced, inserted, duplicates, source-validation rejections, processing rejections and outstanding backlog are distinct. There are no indexing, Redis or search-history metrics. Change runtime log levels through `deploy/config/runtime-logging.yaml`; worker exceptions include operation context and retain retryable work.

## Deliberate limitations

One MongoDB member and one broker are not a resilient cluster. The default stack is not sharded; the optional sharded variant above uses single-member shards on one host. Only the Ingestion outbox tables are partitioned (see above); MongoDB collections are not partitioned. Elasticsearch runs only on the `cs-sharded` stand (single node, no replicas, no auth). No Redis, Neo4j, identity accounts or competition CRUD are implemented in this slice. A 5,000 documents/s setting is not a throughput guarantee. DB tests and benchmarks must identify their actual environment; UI fixture screenshots are not proof of a live database flow.

## Verified failure handling

Malformed JSON and non-object messages are retried up to five processing attempts and quarantined. Invalid retry headers start at attempt one; republished messages carry a validated integer. Only messages with valid job and batch UUIDs invoke the job-failure callback. Uncorrelated poison messages remain in the error queue for inspection, since no job can be safely identified. Completion redrive is explicit and bounded.

The isolated 18 November acceptance also exercised SIGKILL, broker outage, concurrency, real database-unavailable UI recovery and backup/restore. See `docs/coursework/stages/stage12-summary/results.md` for test scope and evidence; a single database/broker remains a single point of failure.
