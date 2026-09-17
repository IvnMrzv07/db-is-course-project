# System Architecture

## Purpose and status

The system is a website for exploring professional Counter-Strike tournaments, teams, players, match results, statistics, and related content. It is a semester project implemented by a team of four. The backend implementation language is Python.

The agreed architecture consists of six independently deployable microservices. Each service uses layered architecture, hexagonal architecture, and explicit CQRS. HTTP supports immediate operations; RabbitMQ supports background commands and integration events. Async I/O supports concurrent network and database operations, while separate worker processes execute background and CPU-intensive work. The coursework additionally requires a high-volume text pipeline, a primary NoSQL corpus distributed over at least three shards, normalized search caching, and a live operational dashboard.

This document defines the architectural baseline. Typed class stubs and composition roots now exist, but runtime behavior is not implemented. Package structures are specified in [Service structure](service-structure.md), class details in [Code inventory](code-inventory.md), and interactions in [Diagrams](diagrams.md). Confirmed decisions and open choices are recorded separately in [Project decisions](project-decisions.md).

The [coursework requirements and acceptance plan](coursework-requirements.md) specifies the revised topology, mandatory tests, measurable targets, report requirements, and source ambiguities. It is part of this architecture, not an optional appendix.

## Product scope

| Capability | User-visible behavior |
| --- | --- |
| Tournament explorer | Browse tournaments, filter by available dates, location, and prize pool, and inspect participants and results. |
| Team and player profiles | View identities, extended profiles, available roster information, and recorded match histories. |
| Match explorer | Filter historical matches and inspect opponents, series scores, map results, lineups, and available player statistics. |
| Team comparison | Compare head-to-head results and win rates within a selected period, with the sample size and data coverage made visible. |
| Personal collection | Register, sign in, and bookmark players, teams, and tournaments. |
| Content and full-text search | Read and search published profiles, biographies, match summaries, articles, and available interviews and highlight links. |
| Relationship explorer | Explore recorded teammates, opponents, team appearances, and sourced membership history. |
| Administration and import | Import data, inspect progress, correct records, resolve ambiguous identities, enrich metadata, and manage publication. |
| Operational dashboard | Adjust document acquisition rate while running; display database-backed write counts/rates, attempted items, backlog, and recent search outcomes with approximately one-second refresh. |
| Explainable recommendations | Recommend recorded games of a selected team or similar players when supported by available statistics; show the selection rule. |

All of these capabilities are in scope, including those initially described as extensions. Missing data can limit individual fields without preventing a profile or tournament page from existing.

The initial scope excludes tournament registration, tournament operation and bracket management, live score feeds, and predictive models. A discipline field permits future expansion, but the first implementation supports Counter-Strike only.

## Source data and enrichment

The initial source is [Counter-Strike Pro Matches on Kaggle](https://www.kaggle.com/datasets/ektarr/counter-strike-pro-matches). The downloaded snapshot was inspected on 2026-09-13.

| File | Observed content |
| --- | --- |
| `players.csv` | 1,398 rows; `player_id` and `player_name`. |
| `teams.csv` | 19,846 rows; `team_id` and `team_name`; 793 distinct team-name strings. |
| `tournaments.csv` | 344 rows; tournament names only. |
| `cs2_all_tiers_games.csv` | 20,676 rows, 9,923 distinct match IDs, dates, teams, lineups, map and series scores, and player statistics. |
| Tier-specific match files | Tier 1, Tier 2, and Tier 3 files. Their overlap with the combined file must be handled during import. |

The combined file contains 9,923 rows with `is_total=True` and 10,753 rows with `is_total=False`. The observed date range is 2023-01-10 through 2026-06-28. These are properties of the inspected snapshot, not guarantees about later releases.

The importer must distinguish series totals from map-level records and must not aggregate both as independent observations. The same match must not be imported repeatedly from the combined and tier-specific files. Source field semantics, including winner flags and aggregate statistics, require validation before calculating derived metrics.

Source team IDs cannot be assumed to identify permanent organizations: 676 distinct team-name strings occur under multiple IDs. Names alone are also insufficient proof of identity. The system assigns internal IDs and records reviewed source-to-internal mappings.

Dedicated fields for biographies, roles, prize pools, tournament locations, founding dates, interviews, and broadcast links are absent. Some player names embed real names and country codes inconsistently.

### Acquisition strategy

1. Import Kaggle match data and available identities.
2. Use PandaScore as the first candidate automated metadata integration.
3. Add Liquipedia through its API if educational access is granted and its coverage is suitable.
4. Use manual curation only when practical automated acquisition cannot provide necessary data or resolve ambiguity.

PandaScore documents a free plan for context data and a separate paid plan for detailed historical statistics. Liquipedia documents educational API access subject to approval. Actual coverage of our entities has not yet been verified through authenticated calls. External accounts, credentials, and paid subscriptions have not been created or authorized by this planning work.

References: [PandaScore pricing](https://www.pandascore.co/pricing), [PandaScore plan reference](https://developers.pandascore.co/docs/plan-reference), [Liquipedia API](https://liquipedia.net/api), and [Liquipedia API terms](https://liquipedia.net/api-terms-of-use). Access details were checked on 2026-09-13 and must be rechecked during integration.

Provider adapters retrieve data in background jobs. User-facing reads use local data. Store provenance, source identifiers, retrieval timestamps, and effective dates where available. Current provider rosters must not replace historical lineups.

Unknown values remain unknown; for example, an unknown prize pool is not zero. Match summaries may be generated from recorded facts, but aggregate statistics do not establish tactical sequences or quotations. Interviews must be sourced rather than fabricated. Synthetic data is reserved for a separate, clearly identified load-test workload.

## Service boundaries and ownership

| Service | Authoritative responsibility | Storage |
| --- | --- | --- |
| `competition_service` | Players, teams, tournaments, matches, maps, player statistics, lineups, verified memberships, accepted competition identity mappings. | PostgreSQL. |
| `content_service` | Primary raw text/metadata corpus, extended profiles, biographies, articles, interviews, highlight metadata, drafts, publication state, and persisted corpus counts. | MongoDB with the high-volume corpus distributed over three shards. |
| `analytics_service` | Derived statistical tables, relationship graph, and processing checkpoints. | Its own PostgreSQL database, Neo4j, and Redis cache. |
| `search_service` | Derived search documents, indexing progress, and bounded recent-query telemetry. | Elasticsearch and Redis search-result cache. |
| `identity_service` | Accounts, roles, and bookmarks. | Its own PostgreSQL database. |
| `ingestion_service` | Import/enrichment/replay jobs, live rate configuration, checkpoints, validation issues, and unresolved identity candidates. | Its own PostgreSQL database and source snapshot file storage. |

Multiple services may share one PostgreSQL server in development, using separate databases and credentials. A service must not query or mutate another service's tables. Redis users have isolated key namespaces and appropriate access controls.

PostgreSQL owns the canonical player identity and competition facts. MongoDB owns the extended profile document keyed by the internal player ID. A name or nationality displayed in several places does not create several authoritative owners. Any copies in content, analytics, or search are explicitly treated as derived values.

Ingestion proposes identity matches; competition accepts and owns the resulting identity mappings. An enrichment job submits changes to the service that owns each fact rather than writing directly to all databases.

Search indexes, analytical projections, graph relationships, and caches are rebuildable. Rebuilding must include publication and removal state so that outdated or unpublished content is not reintroduced.

## Domain model

| Class | Meaning |
| --- | --- |
| `Player` | Stable identity of a professional player. |
| `Team` | Stable identity of a Counter-Strike team. |
| `Tournament` | A particular competition or tournament edition. |
| `Match` | A series between two teams. |
| `MapResult` | Result of one played map within a match. |
| `PlayerMapStats` | A player's available statistics for one map. |
| `MatchLineup` | Players appearing for a team in a particular match. |
| `TeamMembership` | A sourced membership period, where known. |
| `ExternalIdentity` | Provider ID mapped to an internal entity ID. |
| `ExtendedProfile` | Additional sourced or editorial profile content. |
| `Article` | Content with draft and publication state. |
| `Bookmark` | A user's saved reference to a player, team, or tournament. |
| `ImportJob` | Persistent state and progress of an import. |
| `SourceDocument` | Raw text and metadata with provenance, revision, publication eligibility, and real/demo corpus scope. |
| `ReplayJob` | Paced source-file processing with dynamic target rate and durable progress. |

A series result, such as 2-1, is separate from the round score on an individual map. Recorded participation is separate from contractual membership. Shared team membership proves former teammates only when the relevant periods overlap; co-appearance in a recorded lineup is direct evidence of playing together. Data derived from observed participation must not claim exact transfer dates.

Metric formulas, treatment of incomplete matches, and weighting of statistical averages remain implementation specifications to define before building comparisons.

## Internal architecture

The same dependency rules apply to all six services:

- `domain` contains entities, value objects, and business rules, without framework, database, or broker dependencies.
- `application` contains DTOs, application services, repository interfaces, other ports, and application-level mappers.
- Application services are divided into `commands` and `queries`. Commands change authoritative state; queries read local state or projections. Query repositories may return DTOs directly. CQRS does not require event sourcing or separate physical databases inside every service.
- `presentation` contains inbound HTTP and messaging adapters.
- `infrastructure` contains outbound database, provider, broker, search, graph, and cache adapters.
- `bootstrap.py` constructs implementations and injects them into application services.

Repository interfaces are outbound ports even though their folder is named `repositories`. Concrete repositories live in infrastructure. Domain services implement business rules; application services coordinate operations and transactions. API schemas, application DTOs, database models, and domain entities have separate responsibilities.

Mappers belong at the boundary whose representations they understand. A persistence mapper can import ORM models and domain entities; a domain entity cannot import that mapper. Simple conversions may be functions. Straightforward query operations may return application DTOs directly without constructing full domain entities.

This is layered architecture with dependencies directed inward, combined with hexagonal architecture at the application's technology boundaries. See the [original ports-and-adapters description](https://alistair.cockburn.us/hexagonal-architecture).

## HTTP and access boundaries

The browser uses a single reverse proxy/API entry point that routes requests to services. Business logic remains in services. Services enforce authorization rather than trusting routing alone. Administrative import and editing operations require appropriate privileges; users can modify only their own bookmarks.

The following paths illustrate API responsibilities; they are not finalized contracts:

| Operation | Example path | Owner |
| --- | --- | --- |
| Browse tournaments | `GET /tournaments` | Competition. |
| Read a match | `GET /matches/{match_id}` | Competition. |
| Read extended profile content | `GET /profiles/{player_id}` | Content. |
| Compare teams | `GET /comparisons/teams` | Analytics. |
| Explore player relationships | `GET /relationships/players/{player_id}` | Analytics. |
| Full-text search | `GET /search` | Search. |
| Add a bookmark | `POST /bookmarks` | Identity. |
| Start an import | `POST /imports` | Ingestion. |
| Inspect import progress | `GET /imports/{job_id}` | Ingestion. |
| Change replay rate | `PATCH /replays/{job_id}/rate` | Ingestion. |
| Inspect database-backed corpus statistics | `GET /corpus/statistics` | Content. |
| Inspect recent search outcomes | `GET /search/statistics` | Search. |

Long-running operations return a job ID rather than keeping an HTTP request open. Authentication mechanism, endpoint versions, pagination format, and frontend implementation remain open choices.

## Messaging

RabbitMQ carries commands and committed integration events. A command asks one logical owner to perform an action. An event states that a change already occurred. Independent subscribers receive events through their own queues.

| Message | Kind | Producer | Consumer |
| --- | --- | --- | --- |
| `ImportMatchBatch` | Command | Ingestion | Competition. |
| `MatchUpdated` | Event | Competition | Analytics and Search. |
| `PlayerUpdated` | Event | Competition | Analytics and Search. |
| `TeamUpdated` | Event | Competition | Analytics and Search. |
| `TournamentUpdated` | Event | Competition | Analytics and Search as required by their projections. |
| `TeamMembershipUpdated` | Event | Competition | Analytics and Search. |
| `ProfilePublished` | Event | Content | Search. |
| `ArticlePublished` | Event | Content | Search. |
| `ArticleUnpublished` | Event | Content | Search. |
| `ImportBatchCompleted` | Event | Competition | Ingestion. |
| `StoreSourceDocumentBatch` | Command | Ingestion | Content. |
| `SourceDocumentStored` | Event | Content | Search. |
| `DocumentBatchCompleted` | Event | Content | Ingestion. |

The table establishes message responsibilities. Payload schemas, versioning, routing keys, and complete removal/correction events still require specification. A profile or article event must expose only content eligible for indexing, never private drafts.

Messages need unique IDs, schema versions, correlation IDs, and relevant entity IDs and versions. Import commands also need stable job and batch identities. Producers and consumers must agree on whether a payload is a complete projection snapshot or a change requiring an authoritative read.

### Delivery and consistency

Use a transactional outbox for authoritative changes and their pending events. A separate dispatcher publishes committed outbox entries. PostgreSQL changes and outbox entries share a transaction. MongoDB uses an equivalent atomic design and a transaction-capable deployment where multi-document transactions are required.

Use publisher confirms and acknowledge consumed messages only after successful durable processing. Delivery is at least once: consumers must tolerate duplicates. Store processed message identities or use equivalent idempotent updates, and check entity versions to prevent stale events from overwriting newer state. Delta-based projections additionally require gap detection or authoritative recomputation.

Retries are bounded. Persistently failing messages move to a failed-message queue with enough context for inspection and replay. RabbitMQ confirmations do not imply that every downstream service has completed processing. See [RabbitMQ reliability](https://www.rabbitmq.com/docs/reliability).

There is no transaction spanning PostgreSQL, MongoDB, Elasticsearch, Neo4j, and Redis. Authoritative writes are locally transactional; derived data converges asynchronously. Statistical and graph projections have independent checkpoints. The UI distinguishes imported records from fully updated search and analytics.

## Processing flows

### Coursework document acquisition

Ingestion replays prepared domain-text files at a configurable target of 10–5,000 documents/s, with 10–500 as the baseline demonstration range and sustained 5,000 as a stretch target. UI changes apply without restart. Content persists batches in the sharded MongoDB corpus with idempotency and outbox protection; Search indexes committed eligible documents. Database-backed statistics distinguish durable writes from attempted or queued items. A prepared synthetic corpus is isolated from real records and public factual search. The full flow and shard topology are specified in [Coursework requirements](coursework-requirements.md).

### Dataset import

1. An administrator starts an import; ingestion persists an `ImportJob` and returns its ID.
2. A worker reads the source snapshot in bounded batches, validates data, and proposes identity mappings.
3. Ambiguous identities and invalid records are recorded for review. Unresolved records are not silently merged or discarded.
4. Validated batches are submitted to competition with stable batch identities.
5. Competition validates domain rules and transactionally saves accepted records, accepted mappings, and pending events.
6. Its dispatcher publishes events; ingestion records batch outcomes.
7. Analytics and search update their local projections independently.
8. The administration UI reports accepted, rejected, pending, and downstream processing status.

Restarting a job resumes from durable checkpoints. Replaying a completed batch must not duplicate matches or statistics.

### Metadata enrichment

1. Ingestion identifies missing or outdated fields.
2. A worker calls a provider adapter within rate limits and records provenance.
3. Identity resolution connects provider records to internal entities or creates review issues.
4. Proposed canonical changes go to competition; extended content goes to content.
5. Owners validate and commit changes, then publish events for derived data updates.

The application remains usable when a provider is unavailable. Null or omitted provider fields do not automatically erase established values; source precedence and correction rules must be specified.

### Team comparison

1. Analytics validates the requested teams, period, and filters.
2. It checks Redis using a key that includes all query parameters and the relevant data version.
3. On a cache miss, it queries its own statistical tables and builds the comparison DTO.
4. It returns sample size, data coverage, and update timestamp with the result, and caches the response.
5. A corrected match triggers affected aggregate recalculation and cache invalidation or a cache-version change.

Normal comparison requests do not fetch the full history from competition. Cache expiry provides a secondary bound on staleness; exact TTLs remain to be measured and chosen.

### Publication and search

1. An authorized editor publishes content through the content service.
2. Content commits the publication state and pending event atomically.
3. Search consumes the event and updates the appropriate document by entity ID and version.
4. Unpublishing or removal causes the document to be removed or excluded from results.
5. Full-text queries read Elasticsearch. Opening a result retrieves the current authoritative record, which still enforces publication state.

Search results may briefly lag publication changes. No draft content is included in the public index. Search uses Redis for results after versioned query normalization. The default unordered keyword mode lowercases and sorts tokens; filters, corpus, pagination, language, and index version also enter the cache key. Ordered phrase queries must use separate semantics. Return highlighted terms and snippets. Record Found/Empty/Error outcomes for cache hits and misses in bounded search telemetry. Language-aware inflection handling is planned to cover the stricter grading-table wording; the exact language/analyzer remains open.

## Asynchronous execution and scaling

FastAPI is the selected backend API framework. Async-compatible HTTP and database clients support concurrent I/O. Imports, indexing, enrichment, and aggregate recalculation run in worker processes separate from the request-serving processes. CPU-heavy work must not block an API event loop. See [FastAPI concurrency and parallelism](https://fastapi.tiangolo.com/async/).

Scale API processes and worker groups independently. Bound worker concurrency and queue prefetch according to database connections, provider rate limits, and measured capacity. Use batches for imports and indexing. Avoid one message for every scalar field.

The load-test workload is separate from factual production data. Test concurrent browsing, cache hits and misses, batch writes, and downstream processing lag. Record latency percentiles, throughput, queue depth, failures, and resource use. The coursework baseline is search latency below 100 ms at at least 10 RPS. Because no percentile is specified, report p50/p95/p99/max and use p95 < 100 ms as the internal target pending grading interpretation. The 20,676-row snapshot alone is not evidence of high-load capability. Acquisition rate control must cover 10–500 documents/s and permit a 5,000 documents/s stretch experiment; requested rate is distinct from demonstrated durable throughput.

## Verification and operations

Use Pytest to verify domain rules in isolation, repository behavior against real database instances, HTTP and message contracts, and the main import-to-query flow. Mandatory integration tests verify serialization and shard routing without data loss, a stored unique marker found with a snippet/highlight, and an absent marker returning an empty successful result. Reliability checks include duplicate delivery, out-of-order updates, interrupted imports, broker outages, and projection rebuilds. Test effort should target meaningful behavior rather than mirror method implementations.

Track request/job correlation IDs, import counters, projection versions, worker failures, and processing lag. Back up authoritative stores and source snapshots. Derived stores require a tested rebuild procedure. The specific deployment platform, observability stack, retention policy, and recovery objectives have not been selected.

Configure ERROR, WARNING, INFO, and DEBUG levels through configuration files. Include acquisition and query outcomes at INFO and diagnostic database/node timing where available at DEBUG. A one-second polling dashboard obtains metrics from owning services; committed-document counts must be backed by database reads. Prepare measured bottleneck charts, theoretical/practical throughput analysis, and the required report/defense evidence described in the coursework acceptance plan. Replication/failover demonstrations are an additional goal; three replicas of one shard do not satisfy the three-shard requirement.
