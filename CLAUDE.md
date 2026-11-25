# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Coursework project (DB/IS course, Ukrainian-language report and UI) about Counter-Strike esports. Stages 9–12 implement a working corpus pipeline:

**combined CSV (in `counter-strike-pro-matches.zip`) → prepared JSONL → Ingestion (PostgreSQL outbox) → RabbitMQ → Content (MongoDB) → FastAPI → React.**

Only `content_service` and `ingestion_service` have live runtimes on the default stack; `search_service` has a live runtime (Elasticsearch indexer + `/api/v1/search`) only on the `cs-sharded` stand. `competition_service`, `identity_service`, `analytics_service` are future-stage skeletons. Do not assume Redis or Neo4j exist anywhere, or Elasticsearch outside `cs-sharded`. Sharding exists only in the optional `cs-sharded` Compose variant (`deploy/docker-compose.sharded.yml`); partitioning exists only for Ingestion's `replay_batches`/`replay_outbox` (daily `RANGE (created_at)`, see `partitioning.py`). Anything beyond that appears only in target-architecture docs (`docs/architecture.md`, `docs/diagrams/target-modules.mmd`).

## Commands

Python 3.12+. Source root is `backend/` (pytest sets `pythonpath = ["backend", "."]`; for direct runs install editable or set `PYTHONPATH=backend`).

```sh
python -m pip install -r requirements.lock && python -m pip install -e . --no-deps
python -m ingestion_service.infrastructure.datasets.prepare_corpus   # build data/prepared JSONL
python -m pytest -q                                                   # unit/architecture tests, no DBs needed
python -m pytest tests/test_architecture.py::ArchitectureTests::test_inward_dependencies_and_no_cross_service_imports
npm ci --prefix frontend && npm run build --prefix frontend           # tsc --noEmit + vite build
npm run dev --prefix frontend                                          # Vite proxies Content :8000, Ingestion :8001
```

Full stack: copy `.env.example` → `.env`, set `OPERATOR_TOKEN` (≥24 chars), `docker compose up --build -d`, open http://localhost:8080.

- Opt-in real-stack tests: `RUN_STACK_TESTS=1` + `OPERATOR_TOKEN`, then `python -m pytest -m integration -v` (restarts Compose workers/DBs; slow).
- `TEST_MONGO_URL` (replica set required) / `TEST_POSTGRES_URL` enable the real-DB tests in `test_mongo_runtime.py` / `test_postgres_runtime.py`; otherwise they skip.
- Destructive resilience checks run only against the isolated `cs-acceptance` Compose project on port 8081 (`deploy/docker-compose.acceptance.yml`, scripts in `tests/acceptance/`). **Never run `docker compose down -v` against the main project**; its volumes hold the demo corpus.
- High-load stand: `python tools/ops/cs_ops.py --help` (up, start, shard kill/start, verify, purge, reset); measurements in `tools/load/`. `purge` deletes only `load-cs`; `reset` empties every store of the stand, so never run it against a stand whose corpus matters.
- Run APIs/workers manually: `uvicorn content_service.presentation.api.app:app --port 8000`, `uvicorn ingestion_service.presentation.api.app:app --port 8001`, `python -m content_service.worker`, `python -m ingestion_service.worker` (need `MONGO_URL`, `INGESTION_DATABASE_URL`, `BROKER_URL`, `CORPUS_DIR`, `OPERATOR_TOKEN`).

## Architecture

Each `backend/<name>_service/` uses clean/hexagonal layering: `domain/` → `application/` (dtos, ports, repositories as abstract interfaces, `services/commands` and `services/queries` — CQRS split) → `infrastructure/` (adapters) and `presentation/` (`api/controllers`, `messaging/consumers`). Shared message schemas live in `backend/contracts/`.

`tests/test_architecture.py` enforces these rules on every module, so violations fail the normal test suite:
- `domain` imports only stdlib and its own service (no application/infrastructure/presentation/contracts).
- `application` imports only stdlib, its own service, and `contracts` — no third-party libs, no adapters.
- No service imports another `*_service` package.
- Every module must import and its type hints must resolve.
- Every service's `bootstrap.build_container(Settings(service_name=...))` must build a dataclass container with no external connections.

Two composition roots per live service: `bootstrap.py` (connection-free skeleton graph, used by tests) and `runtime.py` (builds the real slice with live Mongo/asyncpg clients, used by `worker.py` and the API app).

Data ownership: Content owns MongoDB `content` (`source_documents`, `committed_batches`, `corpus_counters`, `outbox`); Ingestion owns PostgreSQL tables `replay_jobs`, `replay_batches`, `replay_outbox` (the last two partitioned by day with keys `(id, created_at)`; the worker applies retention, dropping old day partitions only when they hold no unsent/pending rows). Services never read each other's databases — only RabbitMQ (`corpus.store`, `corpus.completed`, plus `<queue>.failed` quarantine after 5 attempts). Both sides use transactional outboxes; MongoDB runs as a single-member replica set (`rs0`) specifically to allow transactions. Nginx (`frontend/nginx.conf`) routes `/api/v1/replays` and `/api/v1/snapshots` to Ingestion, `/api/v1/search` to `search_api` (resolved per request, so the image also runs on stacks without it) and everything else to Content.

Search (cs-sharded only): with `SEARCH_INDEX_EVENTS=1` Content stages a `search.index` event (projection of the batch documents, `contracts.IndexSourceDocuments`) in the same Mongo transaction as the batch; `search_worker` bulk-upserts into ES alias `cs-documents` with `_id` = document id and `version_type=external_gte` (idempotent). ES outage → event requeued, never quarantined. Full reindex: `python -m content_service.reindex` (Content reads its own Mongo, publishes through the broker); index maintenance: `python -m search_service.manage ensure|recreate|status`.

Corpus invariants (see `docs/stages9-12-runtime.md`): document IDs are UUIDv5 over source-scoped keys (`match_id:series` or `match_id:map:game_id`); series and map documents are distinct types and must not be summed together; snapshot CSV SHA-256 and template version are stored per document, and a mismatch for an existing ID is rejected. Expected full import: 20,675 documents, 1 rejected row (CSV line 20100); plus the separate `synthetic-cs` load snapshot (79,325 SDV documents, total 100,000). `load-cs`/`load-cs-random` are unbounded generated snapshots (scope `load-cs`); keep them out of default reads, search and map-reduce.

Operator endpoints need `Authorization: Bearer <OPERATOR_TOKEN>`; starting a replay requires `Idempotency-Key`.

## Docs and conventions

- `docs/stages9-12-runtime.md` (runtime/recovery rules) and `docs/stages9-12-queries.md` (exact query catalogue) are the authoritative descriptions of current behavior; update them when changing runtime semantics.
- Stage deliverables and verification evidence (JSON results) live in `docs/coursework/stages/stageN-summary/`. The report DOCX is at the repo root; `tools/documentation/` holds report/doc generator scripts (maintenance only).
- Runtime log levels: `deploy/config/runtime-logging.yaml`.
- Shell scripts must keep LF line endings (`.gitattributes`). `artifacts/` and `data/prepared/` are ignored local outputs.
