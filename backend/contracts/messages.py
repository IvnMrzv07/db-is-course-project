from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Literal


@dataclass(frozen=True, kw_only=True)
class MessageHeaders:
    """Versioned transport metadata; not a shared domain model."""

    message_id: UUID
    schema_version: int
    correlation_id: UUID
    occurred_at: datetime
    producer: str


@dataclass(frozen=True, kw_only=True)
class ChangeNotification:
    """Reference event: consumers fetch current owner snapshots; removal uses a tombstone.

    Versions are comparable only for the same producer/entity. A consumer recomputes
    from a newer snapshot rather than assuming every intermediate event arrived.
    Never publish draft text or credentials in this envelope.
    """

    headers: MessageHeaders
    event_type: str
    entity_type: str
    entity_id: UUID
    entity_version: int
    corpus_scope: str | None
    deleted: bool = False


@dataclass(frozen=True, kw_only=True)
class BatchCompleted:
    """Durable owner outcome, not an acknowledgement of enqueueing."""

    headers: MessageHeaders
    job_id: UUID
    batch_id: UUID
    job_kind: Literal["match_import", "document_replay"]
    accepted: int
    rejected: int
    source_checkpoint: str


@dataclass(frozen=True, kw_only=True)
class SourceDocumentRecord:
    document_id: UUID
    version: int
    title: str
    text: str
    language: str
    provider: str
    source_id: str
    source_url: str | None
    retrieved_at: datetime
    corpus_scope: str
    is_synthetic: bool
    publication_status: str
    related_entity_ids: tuple[UUID, ...]
    # JSON-typed since template v2 (ints, null, nested `players` list); v1 used only strings.
    metadata: dict[str, object]


@dataclass(frozen=True, kw_only=True)
class StoreSourceDocumentBatch:
    headers: MessageHeaders
    job_id: UUID
    batch_id: UUID
    source_checkpoint: str
    documents: tuple[SourceDocumentRecord, ...]


@dataclass(frozen=True, kw_only=True)
class PlayerStatRecord:
    player_id: UUID
    team_id: UUID
    kills: int | None
    deaths: int | None
    assists: int | None
    adr: float | None
    kast: float | None


@dataclass(frozen=True, kw_only=True)
class MatchRecord:
    """Normalized flat source observation; aggregate rows are distinguished explicitly."""

    source_match_id: str
    source_game_id: str
    provider: str
    tournament_id: UUID
    team1_id: UUID
    team2_id: UUID
    started_at: datetime
    best_of: int
    is_total: bool
    team1_series_score: int | None
    team2_series_score: int | None
    map_name: str | None
    team1_rounds: int | None
    team2_rounds: int | None
    team1_player_ids: tuple[UUID, ...]
    team2_player_ids: tuple[UUID, ...]
    player_statistics: tuple[PlayerStatRecord, ...]


@dataclass(frozen=True, kw_only=True)
class ImportMatchBatch:
    headers: MessageHeaders
    job_id: UUID
    batch_id: UUID
    source_checkpoint: str
    records: tuple[MatchRecord, ...]


@dataclass(frozen=True, kw_only=True)
class ScheduleJob:
    """Durable worker scheduling request emitted with the new job transaction."""

    headers: MessageHeaders
    job_id: UUID
    job_kind: Literal["match_import", "document_replay", "enrichment"]


SEARCH_INDEX_QUEUE = "search.index"
SEARCH_INDEX_EVENT_TYPE = "source_documents.indexable"
SEARCH_INDEX_SCHEMA_VERSION = 1


@dataclass(frozen=True, kw_only=True)
class IndexableSourceDocument:
    """Public projection of one committed Content document for the search index.

    Only published documents are emitted. `version` is the owner's document version and is used
    as the external index version, so redelivery and backfill are idempotent per `document_id`.
    """

    document_id: UUID
    version: int
    title: str
    text: str
    language: str
    corpus_scope: str
    is_synthetic: bool
    source_id: str
    metadata: dict[str, object]


@dataclass(frozen=True, kw_only=True)
class IndexSourceDocuments:
    """`search.index` event (JSON on the wire): Content -> Search, after the owning transaction commits.

    Wire form: {event_id, event_type, schema_version, producer, occurred_at, origin, batch_id, documents[]},
    where origin is "store" (transactional outbox) or "backfill" (full reindex). event_id is
    deterministic for outbox events (`index:<batch_id>`), so a replayed publish is the same event.
    """

    event_id: str
    event_type: str
    schema_version: int
    producer: str
    occurred_at: datetime
    origin: Literal["store", "backfill"]
    batch_id: str
    documents: tuple[IndexableSourceDocument, ...]


OutboxMessage = ChangeNotification | BatchCompleted | ImportMatchBatch | StoreSourceDocumentBatch | ScheduleJob
