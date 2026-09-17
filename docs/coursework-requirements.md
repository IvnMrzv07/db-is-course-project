# Coursework Requirements and Acceptance Plan

## Authority and interpretation

Source: `Курсова робота з Баз даних та інформаційних систем.docx`, reviewed on 2026-09-14, including the grading tables, report requirements, and variant 28. This document maps the brief to the project architecture. It specifies planned acceptance evidence; no implementation or benchmark result is claimed.

The coursework focuses on a distributed, high-load system for data collection, storage, full-text search, and monitoring. The esports website remains the product scope, but its operational dashboard and document pipeline are core deliverables rather than optional administration extras.

## Requirement mapping

| ID | Source requirement | Implementation owner and decision | Acceptance evidence |
| --- | --- | --- | --- |
| C01 | Hexagonal architecture with CQRS or a comparable separation. | All services separate command and query application operations; retain layers and ports/adapters. | Package review and eventual interaction diagram show independent command/query paths. |
| C02 | Configurable acquisition speed from 10 to 500 items/s, preferably 5,000. | Ingestion implements paced file replay, including a prepared corpus of domain-specific text. Configuration supports 10–5,000 documents/s; 10–500 is the baseline demonstration range and 5,000 sustained throughput is a stretch target. | Change the requested rate without restarting; measure actual accepted and durably stored rates separately. |
| C03 | Bulk raw text and metadata in a NoSQL primary store, sharded across at least three nodes. | Content owns a MongoDB source-document corpus distributed over three actual shards. | Show populated shard distribution, routing, and persisted-document verification. Replica members alone do not count as shards. |
| C04 | Full-text search. | Search uses Elasticsearch fed from committed MongoDB corpus/content events. | Relevant results with highlighted terms and snippets; positive and negative marker tests. |
| C05 | Redis/Memcached search-result caching with normalized queries. | Search uses Redis; normalize case, whitespace, and token order for the default unordered keyword mode. | Reordered/case-varied queries reuse a cache key and preserve results. |
| C06 | UI controls acquisition rate and displays live collection/search statistics. | Ingestion, Content, and Search expose query APIs; dashboard polls approximately once per second. | Show attempted resources/records, stored documents, actual write rate, and recent searches with Found/Empty/Error status. |
| C07 | Database-backed demonstration of write speed. | Content samples committed corpus state through database queries; dashboard reads these sampled results. | Stored counts agree with the corpus after quiescence; broker enqueue rate is never presented as database write throughput. |
| C08 | Configurable ERROR, WARNING, INFO, DEBUG logging. | All services load logging configuration from files with deployment overrides. | Demonstrate level changes and representative logs, including operation timing and node details where available. |
| C09 | Automated persistence/shard and search tests. | Pytest integration tests against real MongoDB sharding and Elasticsearch. | Verify serialization, routing, retrieval, and no loss; verify marker found and nonexistent marker empty. |
| C10 | Latency below 100 ms at at least 10 RPS. | Search/API performance baseline. | Report p50, p95, p99, maximum, errors, and cache mix at 10+ RPS. Adopt p95 < 100 ms as an internal target; the brief does not define a percentile, so expose all measurements and confirm evaluation interpretation before defense. |
| C11 | Bottleneck and maximum throughput analysis. | Benchmark acquisition, API, broker, MongoDB, indexing, uncached search, and Redis paths. | Record observed capacity, CPU/I/O/network limits, queue growth, theoretical bounds, and sustainable end-to-end rates. |
| C12 | Throughput diagram and scaling strategies. | Final report includes measured per-component bars/funnel and proposed improvements. | Use project measurements, not the example RPS values in the brief. Diagram remains deferred during current planning. |
| C13 | Required report sections and defense. | Maintain report evidence throughout the semester. | Checklist below, database-console demonstration, and individual team-member explanations. |
| C14 | Domain filtering, navigation, and recommendations. | Competition/Content provide sourced roles, countries, prize pools, memberships, and Twitch links where available; Analytics provides explainable recommendations. | Navigate current/historical teams; filter known values; recommend recorded games or similar players with a visible rule and coverage. |

## Document pipeline and ownership

Add `SourceDocument` to Content: internal ID, source/provenance, title, text, metadata, related entity IDs, retrieval time, revision, publication eligibility, and corpus scope. MongoDB is the primary store for this high-volume text corpus. PostgreSQL remains authoritative for structured match and identity facts; these are complementary responsibilities.

Ingestion owns replay jobs and source snapshots. It reads a prepared file at a controlled rate and sends `StoreSourceDocumentBatch` commands to Content. Content validates, idempotently persists documents and pending events, then emits `SourceDocumentStored` and `DocumentBatchCompleted`. Search indexes only eligible documents in the appropriate corpus index. Ingestion records batch completion without calling an enqueued batch durable.

Real acquired documents and generated load documents use separate corpora, indexes, and cache namespaces. The dashboard can select the demonstration corpus. Synthetic text must be clearly labeled and must never appear as a real player interview or factual historical record. Source documents that are not approved for publication remain excluded from public search. Acquisition of real supplementary facts remains the preferred product-data strategy.

Prepared-file replay satisfies the coursework's Path A and avoids making the benchmark depend on third-party API limits. A local generator can create varied Counter-Strike texts with controlled lengths, vocabulary, and unique markers ahead of time. An API enrichment adapter is not claimed to be the optional full website-crawler bonus.

## MongoDB topology and shard key

Use three data shards, each implemented as a replica set, a three-member configuration-server replica set, and a `mongos` router. A local baseline can use one-member data replica sets on each of the three shards plus three configuration servers and one router (seven database/router processes). This demonstrates partitioning but does not tolerate a data-node failure. A resilience profile uses three members per data shard (nine data members, three configuration members, and at least one router); multiple processes on one host do not provide host-level resilience.

Shard the high-volume source-document collection on hashed `_id`, using stable application-assigned IDs preserved on retries. This avoids a monotonically increasing ingestion-time hotspot and supports targeted ID retrieval. Queries lacking the shard key can scatter across shards; full-text queries use Elasticsearch. Do not use the constant Counter-Strike discipline as the shard key. Population and chunk distribution across all three shards must be checked rather than inferred from configuration.

Writes go through `mongos` to the relevant shard primary. Use acknowledged writes with the selected durability settings recorded in benchmark results; the planned resilient profile uses majority write concern. Read from primaries for the baseline committed-count demonstration. Replica-read experiments, their possible staleness, and failover behavior belong to the resilience evaluation. Configuration nodes and replica copies are not extra partitions.

MongoDB supports hashed sharding and routes data through shards, configuration servers, and routers: [sharding overview](https://www.mongodb.com/docs/manual/sharding/), [deployment guidance](https://www.mongodb.com/docs/manual/tutorial/deploy-shard-cluster/). Exact pinned versions and machine sizing remain implementation choices. Cross-shard outbox transactions may constrain throughput; measure this cost rather than silently relaxing atomicity.

## Search semantics and caching

The default search mode is unordered keyword matching. Normalize Unicode, lowercase, tokenize, collapse whitespace, and sort tokens using a versioned normalization policy. Include corpus scope, filters, language/analyzer version, pagination, sort, and index generation in the cache key. Phrase/ordered modes, if added, must preserve order and use different keys. Cache empty results with a bounded lifetime as well as successful results.

The prose treats stemming/lemmatization as optional bonus work, but the cache grading row mentions inflection handling as mandatory. Plan language-aware normalization and tests for the chosen corpus language to cover the stricter wording. Do not claim generic multilingual equivalence. Use compatible analysis for indexing, querying, and any cache equivalence; preserve player nicknames and other proper names where needed. See [Elasticsearch language analysis](https://www.elastic.co/docs/reference/text-analysis/analysis-lang-analyzer). The supported language and exact analyzer remain to be selected.

Cache IDs/ranking and generate snippets/highlights consistently from the canonical query, or include presentation-sensitive details in the key. Set a bounded TTL and advance index-generation/cache versions after updates. Authoritative content reads still enforce publication status.

## Dashboard and persisted telemetry

Use approximately one-second polling initially; SSE/WebSockets are unnecessary for this requirement. Show requested replay rate, actual attempt rate, durable insert rate, total attempted items/resources, committed documents, rejected items, queue backlog, indexing lag, and latest sample time. Changing or pausing the producer does not instantly eliminate queued writes; show backlog explicitly.

Content obtains committed-document counts through database-backed sampling, using indexed per-run time ranges or verified committed-batch records and periodically reconciling with corpus counts. Avoid a full corpus scan every second. Acknowledgements and timestamps define measurement intervals; retries must not increment unique stored-document totals twice.

Search stores a bounded recent-query history in a service-owned Elasticsearch telemetry index, including normalized query, timestamp, result count, Found/Empty/Error status, duration, and cache-hit flag. Cache hits are recorded too. Ingestion does not read Content or Search databases directly; the dashboard queries their APIs. No seventh monitoring microservice is required.

## CQRS and module changes

Within every service, use `application/services/commands` and `application/services/queries`, with corresponding DTO groups where useful. HTTP POST/PUT/DELETE and message consumers invoke command operations; GET paths invoke query operations. A query may record telemetry or use a cache without modifying authoritative business state. The same local database may support both sides. CQRS does not imply event sourcing.

Competition and Content are authoritative write owners; Analytics and Search maintain separate read projections. Command completion guarantees the owner's commit, not immediate downstream search visibility. Query repositories may return DTOs directly and are distinct from repositories used to persist domain changes.

## Required tests and performance evidence

- Sharded write test: submit documents with controlled IDs, retrieve and compare their serialized fields, inspect routing/distribution, and demonstrate data across all three shards without assuming that an arbitrary ID must belong to a fixed shard forever.
- Positive search test: persist a document with a unique marker through the normal pipeline, wait for indexing with a bounded deadline, search, and verify its ID and highlight/snippet.
- Negative search test: search for an absent unique marker and receive an empty successful response, not unrelated records or HTTP 500.
- Cache equivalence test: vary case and token order; also prove distinct filters, corpora, and phrase modes do not collide.
- Rate-control test: change from 10 to 500 documents/s during a run and observe database-backed output and queue behavior; attempt 5,000 as a separate capacity experiment.
- Search load test: exercise at least 10 RPS with both cache-hit and cache-miss workloads, including concurrent ingestion, and publish latency distributions and errors.
- Reliability tests: duplicate batches, interrupted imports, failed indexing, stale events, publication removal, and independent projection rebuilds.

Record hardware, database topology, dataset size, text-length distribution, concurrency, duration, warmup, cache state, write concern, refresh settings, and software versions. Separate source documents/s from search requests/s. Stable capacity requires bounded queues and error rates, not a short burst of successful enqueue operations.

## Final report and defense checklist

1. Title page, contents, and mapping of semester tasks to report sections.
2. Introduction: relevance, objective, problem statement, subject, and variant.
3. Domain description, entities, relationships, and supporting features.
4. System/module diagram and database topology diagram with shards and read/write routes.
5. Technology rationale, acquisition implementation, dynamic rate control, and search normalization/cache design.
6. Unit/integration evidence, write/search tests, RPS/latency charts from 10 RPS, and INFO/DEBUG/ERROR log examples.
7. Measured throughput diagram, theoretical and practical capacity calculations, bottlenecks, and scaling strategies.
8. Rejected or revised approaches, limitations, and reasons.
9. Conclusions, individual learning outcomes, and future work.
10. Live system, code, and database-console demonstration; each member must explain CAP tradeoffs, query plans, sharding, and replication.

## Grading ambiguities and bonus scope

The introduction describes a 50/50 implementation/defense split, while the detailed base table assigns 40 points to database/query architecture, 15 to results/performance, 15 to UI, and 30 to overall quality/defense. Preserve both statements; do not invent a reconciled weighting. The document states a 60-point minimum and a final cap of 100, with up to 25 bonus points subject to minimum completion of each base category.

Replication offers up to 10 bonus points; advanced features collectively offer up to 15 (crawler, more than three database technologies, exceptional UI, and reactive stack are listed). Bonuses are not guaranteed by selecting technologies. Baseline search, storage, UI, tests, and logging take priority. The existing five-store design and async plan can support bonus evidence; the replication profile is an additional demonstration goal.

The brief's sample throughput numbers and broad claims that SQL cannot meet 10 RPS or that graph traversal has constant performance are illustrative, not measured facts about this system. Database choices must be justified by query patterns and our own benchmarks. The source also mislabels the generator path once; use the actual descriptions of Paths A/B/C rather than that cross-reference.
