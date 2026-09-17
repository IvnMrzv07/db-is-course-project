# Architecture Skeleton Guide

## Deliverable

The source tree now contains typed Python class stubs for all six services. It implements the structure requested by the next assignment: domain records, principal fields, application DTOs, CQRS services, CRUD repository ports, controllers, mappers, and technology adapter classes. It also contains composition roots and editable Mermaid diagrams.

This is an importable architecture skeleton, not a running website. Business operations and external I/O explicitly raise `NotImplementedError`. Constructing a container opens no database or network connections. No real service credentials are included.

## Entry points

| Service | Composition root | Representative class path |
| --- | --- | --- |
| Competition | `competition_service/bootstrap.py` | `presentation/api/controllers/match_controller.py` |
| Content | `content_service/bootstrap.py` | `application/services/commands/source_document_command_service.py` |
| Analytics | `analytics_service/bootstrap.py` | `application/services/queries/comparison_service.py` |
| Search | `search_service/bootstrap.py` | `application/services/queries/search_service.py` |
| Identity | `identity_service/bootstrap.py` | `application/services/commands/account_command_service.py` |
| Ingestion | `ingestion_service/bootstrap.py` | `application/services/commands/replay_command_service.py` |

Paths in the last column are relative to the corresponding service package. The [code inventory](code-inventory.md) links every declared class. The [diagrams](diagrams.md) illustrate the implemented class dependencies and planned runtime flows.

## Code conventions

- `domain/entities` contains independent dataclasses. Null fields represent genuinely unknown values; they are not replaced with zero.
- `application/dtos` contains input/output dataclasses. Update DTOs represent full replacement with an expected version. Partial-patch semantics are not silently inferred from optional fields.
- `application/repositories` contains service-local CRUD protocols. CRUD persistence is not equivalent to exposing unrestricted public CRUD endpoints.
- `application/ports` contains specialized read, projection, cache, provider, pacing, and transaction protocols.
- `application/services/commands` contains state-changing orchestration; `queries` contains reads.
- `presentation/api/controllers` contains named HTTP controller classes. Simple CRUD controllers delegate; specialized controllers declare the intended boundary and remain stubs. FastAPI decorators, transport validation, status/error mapping, and authenticated principal injection are future implementation work.
- `presentation/messaging/consumers` delegates to command services. Broker setup and acknowledgement mechanics remain unimplemented.
- `infrastructure` contains explicitly named technology adapters. CRUD adapters nominally implement repository protocols; specialized adapters structurally implement their ports through matching typed methods.
- `bootstrap.py` constructs a typed object graph with adapters injected into application services. Runtime request/job scoping is not yet implemented; transaction adapters must not become concurrently shared mutable sessions.
- Mappers demonstrate explicit API, DTO, and persistence boundaries. Full persistence mappings and transport schemas remain implementation work rather than pretending the skeleton is production-ready.

The generic CRUD interface exists service-locally for consistency, but Analytics and Search expose specialized read/projection ports rather than public CRUD over derived data. Nested match statistics and lineups have concrete data fields. Identity uses account and bookmark operations and never returns a password hash in its account DTO.

## Integration contracts

`contracts/messages.py` is a transport-only package. It contains no service domain imports and is not a shared database model. In an independently deployed system each service must package a compatible contract version.

`MessageHeaders` defines message identity, schema version, correlation, timestamp, and producer. `ImportMatchBatch` and `StoreSourceDocumentBatch` have stable job/batch IDs and explicit payload records. `BatchCompleted` identifies whether it completes a match import or a document replay and reports durable owner results. `ScheduleJob` represents durable worker scheduling.

`ChangeNotification` is the transport envelope for named events such as `MatchUpdated` or `SourceDocumentStored`; the name is its `event_type`. It references an owner/entity version rather than carrying unpublished text. Consumers fetch current eligible snapshots and apply idempotent projection updates or tombstones. The fetch, HTTP clients, retry behavior, and projection transactions are still adapter implementation work.

Outbox staging and idempotency receipt methods are explicit on the unit-of-work port. Event processing must not claim exactly-once delivery. Version comparison is scoped to the same producer/entity; a combined search document needs separate source-version bookkeeping.

## Verification

Use Python 3.12 or later from the repository root:

```bash
python -m unittest discover -s tests -v
```

The same tests are compatible with Pytest:

```bash
python -m pytest
```

Pytest is declared as an optional test dependency, not required for importing the skeleton. The available runtime did not have Pytest installed, so the delivered checks were executed using unittest. The suite checks imports and resolved type annotations, inward dependencies, cross-service isolation, all six composition roots, CQRS folders, safe account DTOs, trusted actor mapping, controller delegation, and explicit failure of unimplemented repository I/O.

These checks do not satisfy the later database/sharding, marker-search, or performance integration tests. Those require working infrastructure. No throughput, latency, sharding, authentication, or replication result is claimed.

## Changes from the planning trees

The code uses explicit `controllers` folders instead of route-only examples, separates CRUD command/query DTOs, and supplies nominal or structural typed ports. Supporting match entities have persistence ports, while public operations are organized around the primary records. Search and graph integrations are represented by focused query/projection adapters. Some previously proposed filenames have been consolidated; the code inventory and current service-structure document reflect the files that actually exist.

The initial boilerplate was produced by one-time scaffolding scripts, which are excluded from the shared repository because source has been refined after generation. Edit the service files directly. The retained maintenance tools update documentation and diagram exports; see [Maintenance tools](../tools/README.md).

## Remaining implementation decisions

The skeleton does not select a frontend framework or authentication mechanism. The earlier recommendations for React, cookies, and Docker Compose remain recommendations. Search DTOs carry an explicit language and mode without claiming multilingual support. Provider adapters remain conditional on actual access. Database drivers, runtime frameworks, topology deployment, precise metric formulas, final API serialization, cache/analyzer details, and performance measurement remain as recorded in the decision register.
