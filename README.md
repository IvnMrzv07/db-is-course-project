# Counter-Strike corpus explorer

Stages 9–12 implement a local corpus browser and background import pipeline:

**combined CSV → prepared JSONL → Ingestion/PostgreSQL outbox → RabbitMQ → Content/MongoDB → FastAPI → React.**

The default stack runs MongoDB as one single-member replica set for transactions. The optional `cs-sharded` stand (below) adds MongoDB sharding over 3 shards, map-reduce aggregation across shards and Elasticsearch full-text search; Ingestion's replay tables are partitioned by day on both stacks. The full corpus is 100,000 documents (`kaggle-cs` 20,675 + `synthetic-cs` 79,325). **Redis and graph databases are not used** (relationship queries are planned on PostgreSQL). Competition, Identity and Analytics retain their skeletons.

## Start with Docker Compose

1. Install Docker Engine with Compose v2 (Docker Desktop with Linux containers on Windows).
2. Copy `.env.example` to `.env`. Set a random `OPERATOR_TOKEN` of at least 24 characters. Existing PostgreSQL volumes require their existing `POSTGRES_PASSWORD` (the earlier coursework default was `postgres`).
3. Run `docker compose up --build -d` from this directory.
4. Open http://localhost:8080. On **Імпорт та моніторинг**, enter the token, select `kaggle-cs`, and start a replay.
5. Browse documents on **Корпус документів**. The prepared snapshot contains **20,675 accepted records** and **one rejected source row** (CSV line 20100, missing `team1`).
6. Optional load test: select `synthetic-cs · синтетичні (навантажувальні)` to import 79,325 SDV-generated, pseudonymized documents (20,675 + 79,325 = 100,000). They are stored under `corpus_scope=synthetic-cs` and never shown as real matches.

The preparation container creates the JSONL volume automatically. Database initialization is repeatable and preserves existing data. Only the web port is published, bound to localhost. `docker compose down` preserves volumes; do not add `-v` when testing persistence. The single MongoDB member does not provide failover. The stack is a local coursework environment, not a public deployment.

Useful commands:

```sh
docker compose ps
docker compose logs --tail=100 ingestion_worker content_worker
docker compose restart ingestion_worker content_worker
docker compose exec mongo mongosh content --eval 'db.source_documents.countDocuments({})'
```

## Local checks

Python 3.12+:

```sh
python -m venv .venv
# Activate .venv, then:
python -m pip install -r requirements.lock
python -m pip install -e . --no-deps
python -m ingestion_service.infrastructure.datasets.prepare_corpus
python -m pytest -q
npm ci --prefix frontend
npm run build --prefix frontend
```

The synthetic snapshot `data/synthetic/synthetic-cs.csv.gz` is committed input; `prepare_corpus` converts it automatically. To regenerate it (offline, CPU, about 13 minutes):

```sh
python -m venv .venv-synth
.venv-synth/Scripts/python -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
.venv-synth/Scripts/python -m pip install -r requirements-synthetic.txt
PYTHONPATH=backend .venv-synth/Scripts/python -m ingestion_service.infrastructure.datasets.synthesize_corpus
```

See `docs/stages9-12-runtime.md` (section *Synthetic load corpus*) for constraints and `data/synthetic/synthetic-cs.quality.json` for SDMetrics results.

The ordinary tests do not start databases. Real-stack acceptance is opt-in: set `RUN_STACK_TESTS=1` and `OPERATOR_TOKEN`, then run `python -m pytest -m integration -v` from the repository root. It creates replay jobs and restarts the local Compose workers/databases. Allow up to ten minutes per import. It never removes volumes.

On Windows, open a new terminal after installing Docker Desktop so its credential helper is on PATH. Shell scripts must keep LF line endings (enforced by `.gitattributes`).

The full Compose acceptance passed on 17 November 2026: 20,675 stored documents, repeat import without new documents, pause/rate changes, worker restart and database restart persistence. See `docs/coursework/stages/stage12-summary/compose-check.json` and the stage 12 results for evidence. The 35 non-stack tests also passed against the container databases.

A separate real MongoDB test uses `TEST_MONGO_URL` (replica set required) and a uniquely named temporary database. A separate real PostgreSQL test uses `TEST_POSTGRES_URL` and creates/removes only a uniquely named test schema. The normal suite reports it skipped without this variable.

Frontend development: `npm run dev --prefix frontend`; Vite proxies Content to port 8000 and Ingestion to port 8001. Start APIs using `uvicorn content_service.presentation.api.app:app --port 8000` and `uvicorn ingestion_service.presentation.api.app:app --port 8001` after configuring `MONGO_URL`, `INGESTION_DATABASE_URL`, `BROKER_URL`, `CORPUS_DIR`, and `OPERATOR_TOKEN`. Workers run as `python -m content_service.worker` and `python -m ingestion_service.worker`.

## Architecture and evidence

- [Current runtime and recovery](docs/stages9-12-runtime.md)
- [Exact query catalogue](docs/stages9-12-queries.md)
- [Stage 9 decisions](docs/coursework/stages/stage9-summary/decisions.md)
- [Stages 10–11 data and checks](docs/coursework/stages/stage10-11-summary/results.md)
- [Stage 12 UI and demonstration](docs/coursework/stages/stage12-summary/results.md)
- [Sharded MongoDB cluster evidence](docs/coursework/stages/sharding-summary/results.md)
- [PostgreSQL outbox partitioning and retention evidence](docs/coursework/stages/partitioning-summary/results.md)
- [Target architecture](docs/architecture.md) and [decision register](docs/project-decisions.md)

The existing `bootstrap.py` graphs remain importable without connections for skeleton inspection. The new `runtime.py` composition roots explicitly construct the implemented corpus/replay slices with live infrastructure. Application ports remain standard-library-only; controllers delegate through services to repositories.

## Sharded MongoDB variant (optional)

`deploy/docker-compose.sharded.yml` runs the whole stack as a separate Compose project, `cs-sharded`, with its own volumes. MongoDB runs as a config server replica set, three shard replica sets and a `mongos` router. `content.source_documents` is sharded by `{_id: "hashed"}`. Stop the main stack first with `docker compose stop` (never `down -v`):

```sh
docker compose -f deploy/docker-compose.sharded.yml --env-file .env up --build -d   # UI: http://localhost:8082
```

Importing both snapshots yields 100,000 documents spread about 33 % per shard. Evidence (`getShardDistribution`, targeted vs. scatter-gather `explain`) is in [docs/coursework/stages/sharding-summary/](docs/coursework/stages/sharding-summary/results.md).

### Full-text search (Elasticsearch)

The sharded stand also runs Elasticsearch 8 (single node, 512 MB heap, no auth/TLS), `search_worker` and `search_api`. Every batch committed by Content stages a `search.index` event in its transactional outbox; the worker upserts the documents idempotently (document id + external version). The UI tab «Повнотекстовий пошук» (`/#search`) calls `GET /api/v1/search` (modes `all|any|phrase|fuzzy`, filters `corpus_scope`, `document_type`, `map_name`, `include_synthetic`; `_score` and highlights). To index an already loaded corpus:

```sh
docker compose -f deploy/docker-compose.sharded.yml --env-file .env run --rm --no-deps -T content_worker python -m content_service.reindex
docker compose -f deploy/docker-compose.sharded.yml --env-file .env run --rm --no-deps -T search_api python -m search_service.manage status --wait-count 100000
```

Evidence (100,000 indexed documents, event path, examples, timings, degraded state): [docs/coursework/stages/search-summary/](docs/coursework/stages/search-summary/results.md).

## Partitioned Ingestion outbox

`replay_batches` and `replay_outbox` in the Ingestion PostgreSQL database are partitioned by `created_at`. There is one partition per UTC day plus a `DEFAULT` fallback. Services convert an existing database in place on start. The ingestion worker creates upcoming partitions and drops day partitions older than `REPLAY_PARTITION_RETENTION_DAYS` (default 7), but only when they hold no unsent outbox rows and no pending batches. Inspect or clean up manually inside the ingestion container:

```sh
python -m ingestion_service.infrastructure.database.partitioning --report
python -m ingestion_service.infrastructure.database.partitioning --cleanup --dry-run
```

Details: [runtime rules](docs/stages9-12-runtime.md). Evidence: [docs/coursework/stages/partitioning-summary/](docs/coursework/stages/partitioning-summary/results.md).

## Additional acceptance and UI review

The 18 November checks cover forced worker termination, RabbitMQ outage, concurrent operations, malformed-message quarantine, completion redrive, real UI database-outage recovery, backup restoration and Chrome/Edge accessibility checks. Evidence is in `docs/coursework/stages/stage12-summary/results.md` and the accompanying JSON files. The DOCX contains the updated results.

Destructive fault checks use **only** project `cs-acceptance`, port 8081 and explicitly isolated volumes. Its prepared fixture contains the first 1,000 validated records; it is not the full-corpus demonstration. Build the main images first, set `HTTP_PORT=8081`, then run:

```sh
docker compose -p cs-acceptance -f docker-compose.yml -f deploy/docker-compose.acceptance.yml up --no-build -d
python tests/acceptance/verify_stack_resilience.py
node tests/acceptance/verify_ui_outages.cjs
docker compose -p cs-acceptance -f docker-compose.yml -f deploy/docker-compose.acceptance.yml stop
```

Supply `OPERATOR_TOKEN` from your local `.env` and Docker's bin directory on PATH. Browser scripts also use `PLAYWRIGHT_MODULE` and `CHROME_PATH`. `verify_stack_resilience.py` expects fresh acceptance data and exits on a nonempty corpus; resetting its volumes is a deliberate test-only operation, never run `down -v` against the main demo. `verify_ui_outages.cjs` adds 21 paused jobs solely to test history pagination.

## Repository layout

- `backend/`: Python packages. Content and Ingestion implement the current runtime; Competition, Identity, Analytics and Search retain future-stage skeletons. Package import names are unchanged.
- `frontend/`: React application and its Nginx configuration.
- `deploy/`: Compose overrides, database initialization and runtime logging configuration.
- `docs/`: architecture, runtime instructions and query catalog; `docs/diagrams/` contains editable diagrams and images.
- `docs/coursework/stages/`: stage deliverables and committed verification evidence.
- `docs/coursework/requirements/`: original assignment document.
- `tests/`: automated Python suite; `tests/acceptance/` contains explicit browser and Docker validation scripts. Run scripts from the repository root.
- `tools/documentation/`: documentation generators and historical report migration scripts. These are maintenance tools, not application startup steps.
- `artifacts/`: ignored local previews, backup dumps and transient test output.
- `data/prepared/`: ignored generated corpus; the source archive remains at the root for reproducible Docker builds.

The report DOCX currently remains at the root because it was open in Word during the reorganization. No duplicate report is maintained. Existing virtual environments and tool caches are ignored local dependencies.

For direct Python commands, install the project editable as above, or set `PYTHONPATH=backend`. Docker sets `/app/backend` automatically; pytest configures the same source root. The Compose project name and persistent volume names are unchanged.
