# Counter-Strike Information System

This repository contains the planning documents and typed Python architecture skeleton for a database and information systems course project on esports tournaments and players. The first implementation focuses on Counter-Strike.

- [Architecture](docs/architecture.md): service boundaries, data ownership, communication, processing flows, and consistency rules.
- [Service structure](docs/service-structure.md): the agreed layered and hexagonal Python package structure for all six services.
- [Project decisions](docs/project-decisions.md): the consolidated decision register, constraints, source strategy, and unresolved implementation choices.
- [Coursework requirements](docs/coursework-requirements.md): requirement mapping, three-shard MongoDB topology, CQRS, rate control, monitoring, acceptance tests, and defense evidence.
- [Skeleton guide](docs/skeleton-guide.md): implemented stub scope, entry points, contracts, and verification commands.
- [Code inventory](docs/code-inventory.md): source-linked classes for all services.
- [Module and class diagrams](docs/diagrams.md): Mermaid diagrams based on the current skeleton, with editable sources in `diagrams/`.
- [Diagram images](docs/diagram-images.md): all eight diagrams as PNG images; editable Mermaid sources are retained in `diagrams/`.

The six service packages contain importable dataclasses, DTOs, repository ports, CQRS service classes, controllers, adapters, and composition roots. Business operations and database/network I/O remain explicit `NotImplementedError` stubs. There is no deployed website or working database integration yet. API paths and transport details remain to be finalized.

Run the architecture checks from the repository root with Python 3.12+: `python -m unittest discover -s tests -v`. The same tests can run under Pytest when installed. No database drivers are needed to inspect or import the skeleton.

The inspected dataset snapshot is included as `counter-strike-pro-matches.zip`. Extract it locally when implementing the importer. The architecture document records the verified fields and data-quality limitations; it supersedes the earlier dataset proposal.

The coursework brief is `Курсова робота з Баз даних та інформаційних систем.docx`. The architecture was revised against it on 2026-09-14. The operational document pipeline and dashboard are required deliverables alongside the esports features.

The current Ukrainian report is `Звіт з курсової роботи Кіберспортивні турніри та гравці.docx`. It describes the completed planning and skeleton stage. Its references to SVG exports describe earlier local artifacts; the repository distributes PNG exports and editable Mermaid sources.

Start by reading the architecture, decision register, and skeleton guide, then run the architecture checks above. Implement the existing service files directly; the original one-time scaffolding scripts are intentionally excluded. Frontend, authentication, and deployment choices remain open as documented.

See [Maintenance tools](tools/README.md) for updating generated documentation and diagram images. Node.js is needed only for image exports, not for the Python skeleton.
