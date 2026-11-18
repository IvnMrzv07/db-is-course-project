# Stages 9–12 runtime

## Ownership and boundaries

Content owns `source_documents`, `committed_batches`, `corpus_counters` and `outbox` in MongoDB `content`. Ingestion owns `replay_jobs`, `replay_batches` and `replay_outbox` in its PostgreSQL database. No service reads another service's database. RabbitMQ transports version-1 JSON batches and completions. Nginx routes `/api/v1/replays` and `/api/v1/snapshots` to Ingestion; other API paths go to Content.

The current modules diagram is `docs/diagrams/modules.mmd`. `docs/diagrams/target-modules.mmd` describes future services, sharding and search/cache components, not deployed services.

## Corpus identity and meaning

Only `cs2_all_tiers_games.csv` is read from the bundled ZIP. Stable UUIDv5 IDs use a source-scoped key: `match_id:series` or `match_id:map:game_id`. English templates report recorded facts and preserve missing values. Series rows and map rows are different document types, never independent observations to be summed for statistics. Team strings are source labels, not verified organization identities. Source timestamps have no declared timezone and are preserved without inventing one.

The immutable snapshot's CSV SHA-256 and template version are stored per document. A JSONL SHA-256 protects prepared input. A different snapshot/template for an existing ID is rejected pending an explicit migration. There is no public edit/delete API for this archival slice. `retrieved_at` records the local replay start; `stored_at` records ingestion into MongoDB. `is_synthetic=false` means factual descriptions from source rows, not invented matches.

## Transaction and recovery rules

PostgreSQL atomically stores each job's produced offset, batch identity and outbox payload. Workers claim jobs with row locks and `SKIP LOCKED`. Prepared input is verified on startup. Each job has a persistent next-production time; rate updates and pause/resume are committed immediately. Each job is limited to approximately 1,000 outstanding documents. Actual throughput is measured separately from the requested rate.

MongoDB uses a session transaction with majority write concern for documents, unique batch receipt, counter and completion outbox. A repeated batch returns its original result; a new replay of the same documents reports duplicates. Publisher confirms precede the sent marker; consumer ACK follows persistence. A crash between these actions causes safe redelivery. PostgreSQL completion handling locks the job, counts a batch once, and advances its checkpoint only through contiguous completed batches.

After five handler attempts a message goes to `<queue>.failed`. A failed Content batch also sends a failure completion, marking its job failed. Fix the cause and start a new replay; stable IDs preserve existing documents. Completion messages in `corpus.completed.failed` must be inspected and redriven with `python -m ingestion_service.infrastructure.messaging.redrive corpus.completed` in the worker container. The redrive utility only moves a bounded number of messages, uses confirms, and resets the retry count. Failed jobs are not silently reported complete. Queue backlog includes in-flight/outbox documents, not just RabbitMQ ready messages.

MongoDB and PostgreSQL outboxes are service-owned collections/tables, not direct cross-service queries. Runtime v1 deliberately does not publish search events; no indexer or cache consumer is running.

## API

Public GET endpoints: `/documents`, `/documents/{uuid}`, `/corpus/statistics`. Document lists accept `q` (literal substring, max 200), `document_type=series|map`, exact `team`/`tournament`, inclusive `date_from`/`date_to`, `page` and `page_size` (default 20, max 100). Results sort by stable ID. MongoDB reads have a two-second execution limit. This is a bounded scan for substring matching, not a relevance engine.

Operator endpoints require `Authorization: Bearer <token>`: GET `/snapshots`; GET/POST `/replays`; GET `/replays/{uuid}`; PATCH `/replays/{uuid}/rate`; POST `/replays/{uuid}/pause` and `/resume`. Starting requires `Idempotency-Key` and returns 202. The same key with changed parameters returns 409. Unknown prepared input and invalid values return 422; missing records 404; unavailable databases 503. Live API documentation is available on each service's `/docs` when accessed directly on the internal network.

The UI keeps the operator token only in component memory. Changing away from the import page logs out. Sources are selected from a server allowlist; no arbitrary filesystem paths are accepted.

## Counters and logging

The persistent MongoDB counter changes in the document transaction. The dashboard samples it and sums inserted counts from indexed committed-batch records for a trailing ten-second rate. Duplicates do not raise that counter. Reconcile the counter against `source_documents.countDocuments` during acceptance, rather than scanning the corpus every second.

Attempted/produced, inserted, duplicates, source-validation rejections, processing rejections and outstanding backlog are distinct. There are no indexing, Redis or search-history metrics. Change runtime log levels through `deploy/config/runtime-logging.yaml`; worker exceptions include operation context and retain retryable work.

## Deliberate limitations

One MongoDB member and one broker are not a resilient cluster. No sharding, partitioning, Elasticsearch, Redis, Neo4j, identity accounts or competition CRUD are implemented in this slice. A 5,000 documents/s setting is not a throughput guarantee. DB tests and benchmarks must identify their actual environment; UI fixture screenshots are not proof of a live database flow.

## Verified failure handling

Malformed JSON and non-object messages are retried up to five processing attempts and quarantined. Invalid retry headers start at attempt one; republished messages carry a validated integer. Only messages with valid job and batch UUIDs invoke the job-failure callback. Uncorrelated poison messages remain in the error queue for inspection, since no job can be safely identified. Completion redrive is explicit and bounded.

The isolated 18 November acceptance also exercised SIGKILL, broker outage, concurrency, real database-unavailable UI recovery and backup/restore. See `docs/coursework/stages/stage12-summary/results.md` for test scope and evidence; a single database/broker remains a single point of failure.
