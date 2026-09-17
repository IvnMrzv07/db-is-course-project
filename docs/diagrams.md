# Module and Class Diagrams

The class diagrams reference classes in the current skeleton. Interface realization arrows represent nominal or structural Python protocol implementation. Method execution, HTTP route registration, database topology, and broker operation are planned, not deployed.

Each diagram is also stored as an editable `.mmd` source. The diagrams select representative interactions rather than placing every DTO on one unreadable page; [Code inventory](code-inventory.md) lists the complete class set.

## Modules

[Editable Mermaid source](../diagrams/modules.mmd)

```mermaid
flowchart LR
    UI[Website and dashboard] --> Proxy[Reverse proxy]

        subgraph IngestionGroup[Ingestion]
            direction TB
            Ingestion[ingestion_service]
            IngestionDB[(Job PostgreSQL)]
            Sources[Files and provider APIs]
            Ingestion --> IngestionDB
            Ingestion --> Sources
        end
        subgraph CompetitionGroup[Competition]
            direction TB
            Competition[competition_service]
            CompetitionDB[(Competition PostgreSQL)]
            Competition --> CompetitionDB
        end
        subgraph ContentGroup[Content]
            direction TB
            Content[content_service]
            MongoRouter[mongos]
            MongoShards[(MongoDB: 3 data shards)]
            Config[(Config replica set)]
            Content --> MongoRouter
            MongoRouter --> MongoShards
            MongoRouter -. metadata .-> Config
        end
        subgraph AnalyticsGroup[Analytics]
            direction TB
            Analytics[analytics_service]
            AnalyticsDB[(Analytics PostgreSQL)]
            Neo4j[(Neo4j)]
            AnalyticsCache[(Redis: analytics namespace)]
            Analytics --> AnalyticsDB
            Analytics --> Neo4j
            Analytics --> AnalyticsCache
        end
        subgraph SearchGroup[Search]
            direction TB
            Search[search_service]
            ES[(Elasticsearch)]
            SearchCache[(Redis: search namespace)]
            Search --> ES
            Search --> SearchCache
        end
        subgraph IdentityGroup[Identity]
            direction TB
            Identity[identity_service]
            IdentityDB[(Identity PostgreSQL)]
            Identity --> IdentityDB
        end

    Proxy --> Ingestion
    Proxy --> Competition
    Proxy --> Content
    Proxy --> Analytics
    Proxy --> Search
    Proxy --> Identity
    MQ[RabbitMQ]
    Ingestion <-->|Batches / results| MQ
    Competition <-->|Imports / events| MQ
    Content <-->|Documents / events| MQ
    MQ -->|Changes| Analytics
    MQ -->|Changes| Search

    Analytics -. snapshots .-> Competition
    Search -. snapshots .-> Competition
    Search -. published snapshots .-> Content
    Ingestion -. identity mappings .-> Competition
    Ingestion -. enrichment .-> Content
```

The module overview flows from left to right. Each group keeps a service near its storage. Solid arrows show routing, storage access, and labeled broker traffic; dashed arrows show direct owner-API reads or enrichment submissions. The two Redis symbols are namespaces that may share one deployment. MongoDB represents three data shards plus separate configuration infrastructure.

Files include Kaggle and prepared corpora; provider APIs include PandaScore and optional Liquipedia. Elasticsearch includes corpus and telemetry indexes. All infrastructure remains planned. Class diagrams below show selected fields from the actual Python declarations; optional markers and some collection details are abbreviated for readability. The code inventory contains the full definitions.

## Competition Classes

[Editable Mermaid source](../diagrams/competition-classes.mmd)

```mermaid
classDiagram
    class MatchController {
        MatchCommandService commands
        MatchQueryService queries
    }
    class MatchCommandService {
        MatchRepository repository
        UnitOfWork unit_of_work
    }
    class MatchQueryService {
        MatchRepository repository
    }
    class CreateMatch {
        UUID tournament_id
        UUID team1_id
        UUID team2_id
        datetime started_at
        int best_of
    }
    class UpdateMatch {
        UUID id
        int expected_version
        UUID tournament_id
        UUID team1_id
        UUID team2_id
    }
    class MatchDTO {
        UUID id
        int version
        UUID tournament_id
        UUID team1_id
        UUID team2_id
    }
    class MatchRepository {
        <<interface>>
        create(entity)
        get(entity_id)
        list(limit, offset)
        update(entity, expected_version)
        delete(entity_id, expected_version)
    }
    class PostgresMatchRepository {
        str connection_url
    }
    class UnitOfWork {
        <<interface>>
        add_message(message)
        commit()
        rollback()
    }
    class PostgresUnitOfWork {
        str connection_url
    }
    class Match {
        UUID id
        int version
        UUID tournament_id
        UUID team1_id
        UUID team2_id
    }
    class MapResult {
        UUID id
        int version
        UUID match_id
        str map_name
        int map_number
    }
    class PlayerMapStats {
        UUID id
        int version
        UUID player_id
        UUID team_id
        int kills
    }
    class MatchLineup {
        UUID id
        int version
        UUID match_id
        UUID team_id
        tuple player_ids
    }
    class ImportMatchConsumer {
        ImportMatchService service
    }
    class ImportMatchService {
        MatchRepository repository
        UnitOfWork unit_of_work
    }
    MatchController --> MatchCommandService
    MatchController --> MatchQueryService
    MatchCommandService --> CreateMatch
    MatchCommandService --> UpdateMatch
    MatchCommandService --> MatchRepository
    MatchCommandService --> UnitOfWork
    MatchQueryService --> MatchRepository
    MatchQueryService --> MatchDTO
    PostgresMatchRepository ..|> MatchRepository
    PostgresUnitOfWork ..|> UnitOfWork
    MatchRepository --> Match
    Match *-- MapResult
    MapResult *-- PlayerMapStats
    Match *-- MatchLineup
    ImportMatchConsumer --> ImportMatchService
    ImportMatchService --> MatchRepository
    ImportMatchService --> UnitOfWork
    class Player {
        UUID id
        int version
        str nickname
        str real_name
        str country_code
    }
    MatchLineup --> Player : player_ids
    class Team {
        UUID id
        int version
        str name
        str region
        datetime founded_at
    }
    Match --> Team : team IDs
    class Tournament {
        UUID id
        int version
        str name
        str discipline
        datetime starts_at
    }
    Match --> Tournament : tournament_id
```

## Content Classes

[Editable Mermaid source](../diagrams/content-classes.mmd)

```mermaid
classDiagram
    class ArticleController {
        ArticleCommandService commands
        ArticleQueryService queries
    }
    class ArticleCommandService {
        ArticleRepository repository
        UnitOfWork unit_of_work
    }
    class ArticleQueryService {
        ArticleRepository repository
    }
    class ArticleRepository {
        <<interface>>
    }
    class MongoArticleRepository {
        str connection_url
    }
    class SourceDocumentBatchConsumer {
        SourceDocumentCommandService service
    }
    class SourceDocumentCommandService {
        SourceDocumentRepository repository
        UnitOfWork unit_of_work
    }
    class SourceDocumentRepository {
        <<interface>>
    }
    class MongoSourceDocumentRepository {
        str connection_url
    }
    class SourceDocument {
        UUID id
        int version
        str title
        str text
        str language
    }
    class UnitOfWork {
        <<interface>>
        add_event(event)
        commit()
    }
    class MongoUnitOfWork {
        str connection_url
    }
    class CorpusStatisticsQueryServiceController {
        CorpusStatisticsQueryService service
    }
    class CorpusStatisticsQueryService {
        CorpusStatisticsReader reader
    }
    class CorpusStatisticsReader {
        <<interface>>
        sample(corpus_scope)
    }
    class MongoCorpusStatisticsReader {
        str connection_url
    }
    ArticleController --> ArticleCommandService
    ArticleController --> ArticleQueryService
    ArticleCommandService --> ArticleRepository
    ArticleCommandService --> UnitOfWork
    ArticleQueryService --> ArticleRepository
    MongoArticleRepository ..|> ArticleRepository
    SourceDocumentBatchConsumer --> SourceDocumentCommandService
    SourceDocumentCommandService --> SourceDocumentRepository
    SourceDocumentCommandService --> UnitOfWork
    MongoSourceDocumentRepository ..|> SourceDocumentRepository
    SourceDocumentRepository --> SourceDocument
    MongoUnitOfWork ..|> UnitOfWork
    CorpusStatisticsQueryServiceController --> CorpusStatisticsQueryService
    CorpusStatisticsQueryService --> CorpusStatisticsReader
    MongoCorpusStatisticsReader ..|> CorpusStatisticsReader
    class Article {
        UUID id
        int version
        str title
        str body
        UUID match_id
    }
    ArticleRepository --> Article : stores
    class ArticleDTO {
        UUID id
        int version
        str title
        str body
        UUID match_id
    }
    ArticleQueryService --> ArticleDTO : returns
    class CorpusStatisticsDTO {
        str corpus_scope
        int stored_documents
        float durable_documents_per_second
        datetime sampled_at
        int indexed_documents
    }
    CorpusStatisticsQueryService --> CorpusStatisticsDTO : returns
```

## Analytics Classes

[Editable Mermaid source](../diagrams/analytics-classes.mmd)

```mermaid
classDiagram
    class ComparisonServiceController {
        ComparisonService service
    }
    class ComparisonService {
        StatisticsReader reader
        ComparisonCache cache
    }
    class StatisticsReader {
        <<interface>>
        compare(query)
        recommend_matches(team_id, limit)
    }
    class PostgresStatisticsReader {
        str connection_url
    }
    class ComparisonCache {
        <<interface>>
        get(key)
        put(key, value, ttl_seconds)
    }
    class RedisComparisonCache {
        str connection_url
    }
    class RelationshipService {
        RelationshipReader reader
    }
    class RelationshipReader {
        <<interface>>
        find_connections(player_id, max_depth)
    }
    class Neo4jRelationshipReader {
        str connection_url
    }
    class RecommendationService {
        StatisticsReader reader
    }
    class StatisticsEventConsumer {
        StatisticsProjectionService service
    }
    class StatisticsProjectionService {
        StatisticsProjection projection
    }
    class StatisticsProjection {
        <<interface>>
        apply(event)
        rebuild()
    }
    class PostgresStatisticsProjection {
        str connection_url
    }
    class GraphEventConsumer {
        GraphProjectionService service
    }
    class GraphProjectionService {
        GraphProjection projection
    }
    class GraphProjection {
        <<interface>>
        apply(event)
        rebuild()
    }
    class Neo4jGraphProjection {
        str connection_url
    }
    ComparisonServiceController --> ComparisonService
    ComparisonService --> StatisticsReader
    ComparisonService --> ComparisonCache
    PostgresStatisticsReader ..|> StatisticsReader
    RedisComparisonCache ..|> ComparisonCache
    RelationshipService --> RelationshipReader
    Neo4jRelationshipReader ..|> RelationshipReader
    RecommendationService --> StatisticsReader
    StatisticsEventConsumer --> StatisticsProjectionService
    StatisticsProjectionService --> StatisticsProjection
    PostgresStatisticsProjection ..|> StatisticsProjection
    GraphEventConsumer --> GraphProjectionService
    GraphProjectionService --> GraphProjection
    Neo4jGraphProjection ..|> GraphProjection
    class ComparisonQuery {
        UUID team1_id
        UUID team2_id
        datetime starts_at
        datetime ends_at
        str map_name
    }
    ComparisonService --> ComparisonQuery : input
    class TeamComparisonDTO {
        UUID team1_id
        UUID team2_id
        int head_to_head_matches
        int team1_wins
        int team2_wins
    }
    ComparisonService --> TeamComparisonDTO : returns
    class RelationshipDTO {
        tuple player_ids
        tuple team_ids
        tuple evidence_match_ids
        str relationship_kind
        datetime observed_from
    }
    RelationshipService --> RelationshipDTO : returns
```

## Search Classes

[Editable Mermaid source](../diagrams/search-classes.mmd)

```mermaid
classDiagram
    class SearchServiceController {
        SearchService service
    }
    class SearchService {
        SearchReader reader
        SearchCache cache
        SearchHistory history
    }
    class SearchQueryDTO {
        str text
        str corpus_scope
        str language
        str mode
        tuple filters
    }
    class SearchResultDTO {
        tuple hits
        int total
        str index_generation
        datetime updated_at
    }
    class SearchReader {
        <<interface>>
        search(query)
    }
    class ElasticsearchReader {
        str connection_url
    }
    class SearchCache {
        <<interface>>
        get(key)
        put(key, result, ttl_seconds)
    }
    class RedisSearchCache {
        str connection_url
    }
    class SearchHistory {
        <<interface>>
        record(entry)
        recent(limit)
    }
    class ElasticsearchHistory {
        str connection_url
    }
    class IndexingEventConsumer {
        IndexingService service
    }
    class IndexingService {
        SearchIndex index
    }
    class SearchIndex {
        <<interface>>
        apply(event)
        rebuild(corpus_scope)
    }
    class ElasticsearchIndex {
        str connection_url
    }
    SearchServiceController --> SearchService
    SearchService --> SearchQueryDTO
    SearchService --> SearchResultDTO
    SearchService --> SearchReader
    SearchService --> SearchCache
    SearchService --> SearchHistory
    ElasticsearchReader ..|> SearchReader
    RedisSearchCache ..|> SearchCache
    ElasticsearchHistory ..|> SearchHistory
    IndexingEventConsumer --> IndexingService
    IndexingService --> SearchIndex
    ElasticsearchIndex ..|> SearchIndex
    class SearchHitDTO {
        UUID entity_id
        str entity_type
        str title
        str snippet
        tuple highlights
    }
    SearchResultDTO --> SearchHitDTO : hits
    class SearchHistoryDTO {
        str query
        str corpus_scope
        str status
        int result_count
        float duration_ms
    }
    SearchHistory --> SearchHistoryDTO : records
```

## Identity Classes

[Editable Mermaid source](../diagrams/identity-classes.mmd)

```mermaid
classDiagram
    class AccountCommandServiceController {
        AccountCommandService service
    }
    class AccountCommandService {
        UserRepository users
        PasswordHasher hasher
        CredentialIssuer credentials
        UnitOfWork unit_of_work
    }
    class AccountQueryService {
        UserRepository users
    }
    class AccountDTO {
        UUID id
        str email
        str display_name
        tuple roles
        int version
    }
    class UserRepository {
        <<interface>>
    }
    class PostgresUserRepository {
        str connection_url
    }
    class PasswordHasher {
        <<interface>>
        hash(password)
        verify(password, password_hash)
    }
    class PasswordHashingAdapter {
        str connection_url
    }
    class CredentialIssuer {
        <<interface>>
        issue(user_id)
        revoke(credential)
    }
    class CredentialIssuerAdapter {
        str connection_url
    }
    class BookmarkCommandService {
        BookmarkRepository bookmarks
        UnitOfWork unit_of_work
    }
    class BookmarkQueryService {
        BookmarkRepository bookmarks
    }
    class BookmarkRepository {
        <<interface>>
    }
    class PostgresBookmarkRepository {
        str connection_url
    }
    AccountCommandServiceController --> AccountCommandService
    AccountCommandService --> UserRepository
    AccountCommandService --> PasswordHasher
    AccountCommandService --> CredentialIssuer
    AccountCommandService --> AccountDTO
    AccountQueryService --> UserRepository
    AccountQueryService --> AccountDTO
    PostgresUserRepository ..|> UserRepository
    PasswordHashingAdapter ..|> PasswordHasher
    CredentialIssuerAdapter ..|> CredentialIssuer
    BookmarkCommandService --> BookmarkRepository
    BookmarkQueryService --> BookmarkRepository
    PostgresBookmarkRepository ..|> BookmarkRepository
    class User {
        UUID id
        int version
        str email
        str display_name
        str password_hash
    }
    UserRepository --> User : stores
    class Bookmark {
        UUID id
        int version
        UUID user_id
        str target_type
        UUID target_id
    }
    BookmarkRepository --> Bookmark : stores
    class RegistrationDTO {
        str email
        str display_name
        str password
    }
    AccountCommandService --> RegistrationDTO : input
```

## Ingestion Classes

[Editable Mermaid source](../diagrams/ingestion-classes.mmd)

```mermaid
classDiagram
    class ReplayCommandServiceController {
        ReplayCommandService service
    }
    class ReplayCommandService {
        ReplayJobRepository jobs
        RateController pacer
        DatasetReader reader
        CommandPublisher publisher
        UnitOfWork unit_of_work
    }
    class ReplayJobRepository {
        <<interface>>
    }
    class PostgresReplayJobRepository {
        str connection_url
    }
    class RateController {
        <<interface>>
        set_rate(job_id, documents_per_second)
        acquire(job_id, documents)
    }
    class AsyncioRateController {
        str connection_url
    }
    class DatasetReader {
        <<interface>>
        read_matches(snapshot_path, checkpoint, limit)
        read_documents(snapshot_path, checkpoint, limit)
    }
    class KaggleAndTextFileReader {
        str connection_url
    }
    class CommandPublisher {
        <<interface>>
        publish_match_batch(command)
        publish_document_batch(command)
    }
    class RabbitMQCommandPublisher {
        str connection_url
    }
    class ImportService {
        ImportJobRepository jobs
        DatasetReader reader
        CommandPublisher publisher
        UnitOfWork unit_of_work
    }
    class EnrichmentService {
        MetadataProvider provider
        EnrichmentJobRepository jobs
        IdentityCandidateRepository candidates
        UnitOfWork unit_of_work
    }
    class MetadataProvider {
        <<interface>>
        fetch(entity_type, external_ids)
    }
    class PandaScoreAdapter {
        str base_url
        str api_key
    }
    class LiquipediaAdapter {
        str base_url
        str api_key
    }
    class BatchCompletedConsumer {
        BatchCompletionService service
    }
    class BatchCompletionService {
        ImportJobRepository imports
        ReplayJobRepository replays
        UnitOfWork unit_of_work
    }
    ReplayCommandServiceController --> ReplayCommandService
    ReplayCommandService --> ReplayJobRepository
    ReplayCommandService --> RateController
    ReplayCommandService --> DatasetReader
    ReplayCommandService --> CommandPublisher
    PostgresReplayJobRepository ..|> ReplayJobRepository
    AsyncioRateController ..|> RateController
    KaggleAndTextFileReader ..|> DatasetReader
    RabbitMQCommandPublisher ..|> CommandPublisher
    ImportService --> DatasetReader
    ImportService --> CommandPublisher
    EnrichmentService --> MetadataProvider
    PandaScoreAdapter ..|> MetadataProvider
    LiquipediaAdapter ..|> MetadataProvider
    BatchCompletedConsumer --> BatchCompletionService
    BatchCompletionService --> ReplayJobRepository
    class ReplayJob {
        UUID id
        int version
        str source_snapshot
        str corpus_scope
        str status
    }
    ReplayJobRepository --> ReplayJob : stores
    class StartReplayDTO {
        str snapshot_path
        str corpus_scope
        int target_documents_per_second
        UUID actor_id
        str idempotency_key
    }
    ReplayCommandService --> StartReplayDTO : input
    class JobProgressDTO {
        UUID job_id
        str status
        int attempted
        int accepted
        int rejected
    }
    ImportService --> JobProgressDTO : returns
```

## Document Flow

[Editable Mermaid source](../diagrams/document-flow.mmd)

```mermaid
sequenceDiagram
    actor Admin
    participant RC as ReplayCommandService
    participant R as DatasetReader and RateController
    participant MQ as RabbitMQ with outbox dispatcher
    participant C as SourceDocumentCommandService
    participant CQ as SourceDocumentQueryService
    participant BC as BatchCompletionService
    participant DB as MongoDB via mongos
    participant S as IndexingService
    participant ES as Elasticsearch
    Admin->>RC: start or change_rate
    Note over RC: Persist job/rate, return before processing completes
    RC->>R: read bounded batch and acquire allowance
    RC->>MQ: committed StoreSourceDocumentBatch
    MQ->>C: deliver command
    C->>DB: transaction: documents, receipt, outbox
    DB-->>C: durable commit
    C->>MQ: SourceDocumentStored and DocumentBatchCompleted
    MQ->>BC: BatchCompleted - update durable replay progress
    MQ->>S: reference ChangeNotification
    S->>CQ: read eligible current owner snapshot through owner API
    CQ-->>S: versioned published document or tombstone
    S->>ES: version-aware upsert or removal
    Admin->>C: query database-backed corpus statistics
    Note over Admin,ES: Planned sequence, infrastructure operations are currently stubs
```
