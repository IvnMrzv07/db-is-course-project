# Project Decision Register

## Status and interpretation

This register consolidates the decisions accepted during project planning through 2026-09-14. It separates agreed scope and architecture from details still requiring design or external access.

The architecture task requires layered and hexagonal architecture and a diagram of module and class interactions. The full coursework brief adds CQRS or equivalent separation, sharded primary NoSQL storage, normalized search caching, rate control, monitoring, tests, logging, and performance evidence. Microservices and asynchronous processing remain team-selected requirements; async is additionally encouraged by the brief. The user subsequently authorized the class-skeleton task together with the architecture diagrams; both now have source artifacts. See [Coursework requirements](coursework-requirements.md) for the requirement mapping and ambiguities.

## Confirmed global decisions

| ID | Decision | Consequence |
| --- | --- | --- |
| D01 | Build an informational and analytical website around esports tournaments and players. | Provide browsing, comparisons, content, search, personal collections, and administration. |
| D02 | Support Counter-Strike only in the first implementation. | Retain a discipline field for future expansion; do not implement Dota 2 functionality now. |
| D03 | Include all eight agreed capabilities. | Tournament explorer, profiles, match explorer, team comparison, bookmarks, content/search, relationship exploration, and import/administration are all in scope. |
| D04 | Defer live scores, tournament registration/operation, bracket management, and predictions. | These are not required for the first implementation. |
| D05 | Use Python for the backend. | Use standard Python naming and Python-compatible interfaces and clients. |
| D06 | Use FastAPI for HTTP APIs. | Use async-compatible I/O where beneficial and keep domain logic framework-independent. |
| D07 | Use six microservices. | Competition, Content, Analytics, Search, Identity, and Ingestion have explicit ownership boundaries. |
| D08 | Combine layered architecture with hexagonal architecture inside each service. | Dependency direction points toward domain/application code; external technologies are adapters. |
| D09 | Use conventional folder names consistently. | Use DTOs, services, repositories, mappers, and other ports within the agreed layers. |
| D10 | Separate repository interfaces from implementations. | Interfaces live in `application/repositories`; concrete implementations live in infrastructure. |
| D11 | Distinguish domain services from application services. | Domain services implement rules; application services coordinate use cases, persistence, and transactions. |
| D12 | Compose dependencies in `bootstrap.py`. | Application code does not instantiate concrete infrastructure dependencies. |
| D13 | Give each fact one authoritative owner. | Other stores contain explicitly derived copies or separate complementary facts. |
| D14 | Use PostgreSQL for canonical competition data and relational service state. | Competition, Identity, Ingestion, and Analytics have separate databases as needed. |
| D15 | Use MongoDB for extended profiles and editorial content. | Canonical player identity remains in Competition; MongoDB documents reference internal IDs. |
| D16 | Use Elasticsearch for required full-text search. | Index published content and selected competition data; rebuild from authoritative sources. |
| D17 | Use Neo4j for relationship exploration. | Maintain a derived graph of players, teams, matches, and supported connections. |
| D18 | Use Redis as a cache. | Cache repeated reads and expensive comparisons; do not use it as the sole authoritative store. |
| D19 | Permit shared PostgreSQL infrastructure in development with separate service databases and credentials. | Prohibit cross-service table access and shared database ownership. |
| D20 | Use HTTP for immediate requests and RabbitMQ for background commands/events. | Long-running work returns job IDs; events update downstream projections. |
| D21 | Use a single reverse proxy/API entry point. | Route browser requests centrally while keeping business logic and authorization in services. |
| D22 | Execute background work in separate worker processes. | Imports, enrichment, indexing, and recalculation do not occupy user request lifecycles. |
| D23 | Use bounded concurrency and independent scaling. | Respect provider rate limits, database pools, and measured worker capacity. |
| D24 | Use transactional outbox delivery for committed changes. | Persist pending events atomically with authoritative writes and dispatch them separately. |
| D25 | Assume at-least-once message delivery. | Handle duplicate commands/events, stale versions, bounded retries, and failed-message recovery. |
| D26 | Accept eventual consistency for derived data. | Search, analytics, graphs, and caches can lag; expose relevant progress and timestamps. |
| D27 | Rebuild derived stores from authoritative data. | Search, analytical tables, graphs, and caches are not independent sources of truth. |
| D28 | Use Kaggle as the initial match dataset. | Import the inspected snapshot with validation, deduplication, and identity resolution. |
| D29 | Prioritize automated supplementary acquisition. | Use manual curation only when practical automated sources are insufficient or ambiguity requires review. |
| D30 | Start enrichment with PandaScore; consider Liquipedia API as a second source. | Actual field coverage and account access must be validated; Liquipedia integration is conditional on access. |
| D31 | Serve user reads from local data. | Provider outages do not prevent browsing previously imported records. |
| D32 | Assign stable internal entity IDs. | Maintain provider-to-internal mappings; do not equate a name match with verified identity. |
| D33 | Let Competition own accepted competition identity mappings. | Ingestion proposes mappings and routes ambiguity to review. |
| D34 | Preserve provenance and temporal meaning. | Store source information and available effective dates; current rosters cannot overwrite historical lineups. |
| D35 | Model series, maps, lineups, and memberships separately. | Avoid double-counting aggregate rows or claiming contract dates from match participation. |
| D36 | Permit incomplete records. | Unknown values remain unknown; an unknown prize pool is not zero. |
| D37 | Generate factual summaries only from supported data. | Do not invent tactical events or interviews; source interviews and highlight links where available. |
| D38 | Keep synthetic load data separate from factual records. | Demonstrate write pressure and concurrency without presenting fabricated esports history as real. |
| D39 | Plan for a four-person team over one semester. | Scope is not reduced solely because of a short implementation window. |
| D40 | Use standard technical English in repository planning documents. | Keep terminology consistent across architecture, service structures, and decisions. |
| D41 | Document architecture now and defer diagrams. | The current deliverable is a written planning baseline, not code or a generated diagram. |
| D42 | Make CQRS explicit in every service. | Split application operations into command and query groups; do not introduce event sourcing by implication. |
| D43 | Expand Content to own the primary raw text corpus. | MongoDB stores bulk source documents and metadata in addition to profiles and editorial content. |
| D44 | Shard the MongoDB corpus across three actual data shards. | Use hashed `_id` as the planned shard key; document router/configuration infrastructure and verify populated distribution. |
| D45 | Implement paced file replay with runtime rate control. | Support 10–500 documents/s for baseline demonstrations and configure up to 5,000 for stretch testing; measure actual durable throughput independently. |
| D46 | Add a live operational dashboard. | Approximately one-second polling shows database-backed writes, attempted records, backlog, and recent search outcomes. |
| D47 | Cache normalized full-text search results in Redis. | Normalize unordered keyword queries; include scope/filters/language/version in keys; plan inflection handling for the stricter rubric wording. |
| D48 | Return search snippets and highlights. | Validate relevance, positive markers, and empty results. |
| D49 | Adopt the brief's search performance baseline. | At least 10 RPS and latency below 100 ms; report all percentiles and use p95 < 100 ms internally because the brief does not define the statistic. |
| D50 | Use Pytest for required automated tests. | Include shard routing/serialization/no-loss tests and positive/negative full-text search tests. |
| D51 | Configure log levels through files. | Demonstrate ERROR, WARNING, INFO, DEBUG and relevant operation/node timing. |
| D52 | Include explainable domain recommendations. | Recommend recorded team games or similar players based on supported data, without inventing roles or play styles. |
| D53 | Produce the required report and bottleneck evidence. | Track measured capacities, topology, tests, rejected approaches, scaling strategies, and individual defense preparation. |
| D54 | Separate sharding from replication demonstrations. | Three data shards are mandatory; the resilient three-member-per-shard profile is an additional goal requiring sizing and failover evidence. |
| D55 | Bundle the architecture diagrams with the typed class-skeleton assignment. | Supersedes D41's temporary diagram deferral; provide editable module/class diagrams and Python stubs, not a production implementation. |
| D56 | Use importable standard-library DTO/entity and protocol stubs. | Python 3.12+; external adapters raise `NotImplementedError`. Add actual FastAPI/driver dependencies in the implementation phase. |
| D57 | Use explicit controller classes for the assignment. | Place HTTP adapter stubs under `presentation/api/controllers`; route registration is later implementation work. |
| D58 | Use transport-only shared message contracts. | Stable batch/message IDs, source-scoped versions, current-snapshot reference events, and distinct match-import/document-replay completion kinds. No shared service domain model. |

D42–D54 were added after reviewing the full brief on 2026-09-14. They refine D03, D08, D15–D18, D28, and D38 without removing the previously agreed esports features or changing the six-service boundary. D15 now includes the primary raw corpus; D16 includes recent-query telemetry; D18 explicitly includes normalized search caching. D38 permits prepared generated texts only in isolated demonstration corpora.

D55–D58 record the subsequent skeleton work. React, a cookie-based authentication mechanism, and Docker Compose were discussed as recommendations, not selected requirements. The current stub code does not silently finalize those choices.

## Ownership summary

| Owner | Authoritative data or responsibility |
| --- | --- |
| Competition | Competition facts, identities, lineups, memberships, and accepted source mappings. |
| Content | Primary raw text corpus, extended profiles, sourced/editorial content, publication state, and persisted corpus counts. |
| Identity | Accounts, roles, and bookmarks. |
| Ingestion | Import/enrichment/replay jobs, dynamic rate configuration, review issues, source snapshots, and job progress. |
| Analytics | Rebuildable statistical and graph projections and their progress. |
| Search | Rebuildable search documents, indexing progress, normalized result caching, and bounded recent-query telemetry. |

## Decisions not yet finalized

The following are open design work, not implied commitments:

- Frontend framework, UI design, supported UI languages, and browser compatibility targets.
- Exact API routes, request/response fields, pagination conventions, API versions, and error formats.
- Authentication mechanism, credential lifetime, detailed role/permission matrix, and account recovery behavior.
- Final event schemas, routing keys, queue topology, ordering/gap handling, and removal/correction contracts.
- Metric formulas, weighted aggregation rules, incomplete-match handling, and graph query limits.
- Source precedence, identity-matching thresholds, provider coverage, refresh intervals, and review rules.
- External accounts and credentials. No paid subscription is authorized by selecting a candidate provider.
- Whether match summaries use deterministic templates or an LLM, and whether generation requires editorial approval.
- Exact ORM, database drivers, worker library, dependency manager, and package versions. SQLAlchemy naming in example modules is an implementation candidate, not a pinned dependency decision.
- Search analyzers, supported search languages, ranking configuration, index structure, and reindex strategy.
- Redis TTLs, cache-key versions, invalidation implementation, and cache-failure behavior.
- Runtime deployment platform, reverse proxy product, container setup, CI configuration, and local resource sizing.
- Snapshot storage backend, retention periods, backups, recovery objectives, and observability tooling.
- Benchmark tooling, sustained test durations, hardware sizing, and interpretation of the brief's unspecified latency percentile. Minimum search load/latency and acquisition-control ranges are now defined by D45 and D49.
- Team task allocation and implementation milestones.

## Source references

- [Kaggle dataset](https://www.kaggle.com/datasets/ektarr/counter-strike-pro-matches): initial match source; local snapshot inspected on 2026-09-13.
- [PandaScore pricing](https://www.pandascore.co/pricing) and [plan reference](https://developers.pandascore.co/docs/plan-reference): candidate enrichment access and documented coverage.
- [Liquipedia API](https://liquipedia.net/api) and [API terms](https://liquipedia.net/api-terms-of-use): conditional educational access and required API-based integration.
- [Hexagonal architecture](https://alistair.cockburn.us/hexagonal-architecture): ports-and-adapters dependency principles.
- [RabbitMQ reliability](https://www.rabbitmq.com/docs/reliability): acknowledgements, publisher confirms, and duplicate delivery considerations.
- [FastAPI asynchronous execution](https://fastapi.tiangolo.com/async/): distinction between I/O concurrency and CPU parallelism.

Provider access details can change and should be verified during integration. These references support technical context; the decisions themselves are the team's planning baseline.
