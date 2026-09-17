# Code Inventory

Generated from the current Python source. These are typed architecture stubs, not completed runtime implementations.

## Competition service

| Module | Declared classes |
| --- | --- |
| [application/dtos/match_commands.py](../competition_service/application/dtos/match_commands.py) | `CreateMatch`, `UpdateMatch` |
| [application/dtos/match_components_dto.py](../competition_service/application/dtos/match_components_dto.py) | `PlayerMapStatsDTO`, `MapResultDTO`, `MatchLineupDTO` |
| [application/dtos/match_dto.py](../competition_service/application/dtos/match_dto.py) | `MatchDTO` |
| [application/dtos/player_commands.py](../competition_service/application/dtos/player_commands.py) | `CreatePlayer`, `UpdatePlayer` |
| [application/dtos/player_dto.py](../competition_service/application/dtos/player_dto.py) | `PlayerDTO` |
| [application/dtos/team_commands.py](../competition_service/application/dtos/team_commands.py) | `CreateTeam`, `UpdateTeam` |
| [application/dtos/team_dto.py](../competition_service/application/dtos/team_dto.py) | `TeamDTO` |
| [application/dtos/tournament_commands.py](../competition_service/application/dtos/tournament_commands.py) | `CreateTournament`, `UpdateTournament` |
| [application/dtos/tournament_dto.py](../competition_service/application/dtos/tournament_dto.py) | `TournamentDTO` |
| [application/mappers/match_dto_mapper.py](../competition_service/application/mappers/match_dto_mapper.py) | `MatchDTOMapper` |
| [application/mappers/player_dto_mapper.py](../competition_service/application/mappers/player_dto_mapper.py) | `PlayerDTOMapper` |
| [application/mappers/team_dto_mapper.py](../competition_service/application/mappers/team_dto_mapper.py) | `TeamDTOMapper` |
| [application/mappers/tournament_dto_mapper.py](../competition_service/application/mappers/tournament_dto_mapper.py) | `TournamentDTOMapper` |
| [application/ports/unit_of_work.py](../competition_service/application/ports/unit_of_work.py) | `UnitOfWork` |
| [application/repositories/crud_repository.py](../competition_service/application/repositories/crud_repository.py) | `CrudRepository` |
| [application/repositories/external_identity_repository.py](../competition_service/application/repositories/external_identity_repository.py) | `ExternalIdentityRepository` |
| [application/repositories/map_result_repository.py](../competition_service/application/repositories/map_result_repository.py) | `MapResultRepository` |
| [application/repositories/match_lineup_repository.py](../competition_service/application/repositories/match_lineup_repository.py) | `MatchLineupRepository` |
| [application/repositories/match_repository.py](../competition_service/application/repositories/match_repository.py) | `MatchRepository` |
| [application/repositories/player_map_stats_repository.py](../competition_service/application/repositories/player_map_stats_repository.py) | `PlayerMapStatsRepository` |
| [application/repositories/player_repository.py](../competition_service/application/repositories/player_repository.py) | `PlayerRepository` |
| [application/repositories/team_membership_repository.py](../competition_service/application/repositories/team_membership_repository.py) | `TeamMembershipRepository` |
| [application/repositories/team_repository.py](../competition_service/application/repositories/team_repository.py) | `TeamRepository` |
| [application/repositories/tournament_repository.py](../competition_service/application/repositories/tournament_repository.py) | `TournamentRepository` |
| [application/services/commands/import_match_service.py](../competition_service/application/services/commands/import_match_service.py) | `ImportMatchService` |
| [application/services/commands/match_command_service.py](../competition_service/application/services/commands/match_command_service.py) | `MatchCommandService` |
| [application/services/commands/player_command_service.py](../competition_service/application/services/commands/player_command_service.py) | `PlayerCommandService` |
| [application/services/commands/team_command_service.py](../competition_service/application/services/commands/team_command_service.py) | `TeamCommandService` |
| [application/services/commands/tournament_command_service.py](../competition_service/application/services/commands/tournament_command_service.py) | `TournamentCommandService` |
| [application/services/queries/match_query_service.py](../competition_service/application/services/queries/match_query_service.py) | `MatchQueryService` |
| [application/services/queries/player_query_service.py](../competition_service/application/services/queries/player_query_service.py) | `PlayerQueryService` |
| [application/services/queries/team_query_service.py](../competition_service/application/services/queries/team_query_service.py) | `TeamQueryService` |
| [application/services/queries/tournament_query_service.py](../competition_service/application/services/queries/tournament_query_service.py) | `TournamentQueryService` |
| [bootstrap.py](../competition_service/bootstrap.py) | `Container` |
| [domain/entities/external_identity.py](../competition_service/domain/entities/external_identity.py) | `ExternalIdentity` |
| [domain/entities/map_result.py](../competition_service/domain/entities/map_result.py) | `MapResult` |
| [domain/entities/match.py](../competition_service/domain/entities/match.py) | `Match` |
| [domain/entities/match_lineup.py](../competition_service/domain/entities/match_lineup.py) | `MatchLineup` |
| [domain/entities/player.py](../competition_service/domain/entities/player.py) | `Player` |
| [domain/entities/player_map_stats.py](../competition_service/domain/entities/player_map_stats.py) | `PlayerMapStats` |
| [domain/entities/team.py](../competition_service/domain/entities/team.py) | `Team` |
| [domain/entities/team_membership.py](../competition_service/domain/entities/team_membership.py) | `TeamMembership` |
| [domain/entities/tournament.py](../competition_service/domain/entities/tournament.py) | `Tournament` |
| [domain/exceptions.py](../competition_service/domain/exceptions.py) | `DomainError`, `VersionConflict` |
| [domain/services/match_result_validator.py](../competition_service/domain/services/match_result_validator.py) | `MatchResultValidator` |
| [infrastructure/database/mappers/player_persistence_mapper.py](../competition_service/infrastructure/database/mappers/player_persistence_mapper.py) | `PlayerPersistenceMapper` |
| [infrastructure/database/models/player_model.py](../competition_service/infrastructure/database/models/player_model.py) | `PlayerModel` |
| [infrastructure/database/repositories/postgres_external_identity_repository.py](../competition_service/infrastructure/database/repositories/postgres_external_identity_repository.py) | `PostgresExternalIdentityRepository` |
| [infrastructure/database/repositories/postgres_map_result_repository.py](../competition_service/infrastructure/database/repositories/postgres_map_result_repository.py) | `PostgresMapResultRepository` |
| [infrastructure/database/repositories/postgres_match_lineup_repository.py](../competition_service/infrastructure/database/repositories/postgres_match_lineup_repository.py) | `PostgresMatchLineupRepository` |
| [infrastructure/database/repositories/postgres_match_repository.py](../competition_service/infrastructure/database/repositories/postgres_match_repository.py) | `PostgresMatchRepository` |
| [infrastructure/database/repositories/postgres_player_map_stats_repository.py](../competition_service/infrastructure/database/repositories/postgres_player_map_stats_repository.py) | `PostgresPlayerMapStatsRepository` |
| [infrastructure/database/repositories/postgres_player_repository.py](../competition_service/infrastructure/database/repositories/postgres_player_repository.py) | `PostgresPlayerRepository` |
| [infrastructure/database/repositories/postgres_team_membership_repository.py](../competition_service/infrastructure/database/repositories/postgres_team_membership_repository.py) | `PostgresTeamMembershipRepository` |
| [infrastructure/database/repositories/postgres_team_repository.py](../competition_service/infrastructure/database/repositories/postgres_team_repository.py) | `PostgresTeamRepository` |
| [infrastructure/database/repositories/postgres_tournament_repository.py](../competition_service/infrastructure/database/repositories/postgres_tournament_repository.py) | `PostgresTournamentRepository` |
| [infrastructure/database/unit_of_work_adapter.py](../competition_service/infrastructure/database/unit_of_work_adapter.py) | `PostgresUnitOfWork` |
| [presentation/api/controllers/match_controller.py](../competition_service/presentation/api/controllers/match_controller.py) | `MatchController` |
| [presentation/api/controllers/player_controller.py](../competition_service/presentation/api/controllers/player_controller.py) | `PlayerController` |
| [presentation/api/controllers/team_controller.py](../competition_service/presentation/api/controllers/team_controller.py) | `TeamController` |
| [presentation/api/controllers/tournament_controller.py](../competition_service/presentation/api/controllers/tournament_controller.py) | `TournamentController` |
| [presentation/api/mappers/player_api_mapper.py](../competition_service/presentation/api/mappers/player_api_mapper.py) | `PlayerAPIMapper` |
| [presentation/api/schemas/player_request.py](../competition_service/presentation/api/schemas/player_request.py) | `PlayerRequest` |
| [presentation/messaging/consumers/import_match_consumer.py](../competition_service/presentation/messaging/consumers/import_match_consumer.py) | `ImportMatchConsumer` |
| [settings.py](../competition_service/settings.py) | `Settings` |

## Content service

| Module | Declared classes |
| --- | --- |
| [application/dtos/article_commands.py](../content_service/application/dtos/article_commands.py) | `CreateArticle`, `UpdateArticle` |
| [application/dtos/article_dto.py](../content_service/application/dtos/article_dto.py) | `ArticleDTO` |
| [application/dtos/corpus_statistics_dto.py](../content_service/application/dtos/corpus_statistics_dto.py) | `CorpusStatisticsDTO` |
| [application/dtos/extended_profile_commands.py](../content_service/application/dtos/extended_profile_commands.py) | `CreateExtendedProfile`, `UpdateExtendedProfile` |
| [application/dtos/extended_profile_dto.py](../content_service/application/dtos/extended_profile_dto.py) | `ExtendedProfileDTO` |
| [application/dtos/highlight_commands.py](../content_service/application/dtos/highlight_commands.py) | `CreateHighlight`, `UpdateHighlight` |
| [application/dtos/highlight_dto.py](../content_service/application/dtos/highlight_dto.py) | `HighlightDTO` |
| [application/dtos/interview_commands.py](../content_service/application/dtos/interview_commands.py) | `CreateInterview`, `UpdateInterview` |
| [application/dtos/interview_dto.py](../content_service/application/dtos/interview_dto.py) | `InterviewDTO` |
| [application/dtos/source_document_snapshot_dto.py](../content_service/application/dtos/source_document_snapshot_dto.py) | `SourceDocumentSnapshotDTO` |
| [application/mappers/article_dto_mapper.py](../content_service/application/mappers/article_dto_mapper.py) | `ArticleDTOMapper` |
| [application/mappers/extended_profile_dto_mapper.py](../content_service/application/mappers/extended_profile_dto_mapper.py) | `ExtendedProfileDTOMapper` |
| [application/mappers/highlight_dto_mapper.py](../content_service/application/mappers/highlight_dto_mapper.py) | `HighlightDTOMapper` |
| [application/mappers/interview_dto_mapper.py](../content_service/application/mappers/interview_dto_mapper.py) | `InterviewDTOMapper` |
| [application/ports/corpus_statistics.py](../content_service/application/ports/corpus_statistics.py) | `CorpusStatisticsReader` |
| [application/ports/unit_of_work.py](../content_service/application/ports/unit_of_work.py) | `UnitOfWork` |
| [application/repositories/article_repository.py](../content_service/application/repositories/article_repository.py) | `ArticleRepository` |
| [application/repositories/crud_repository.py](../content_service/application/repositories/crud_repository.py) | `CrudRepository` |
| [application/repositories/extended_profile_repository.py](../content_service/application/repositories/extended_profile_repository.py) | `ExtendedProfileRepository` |
| [application/repositories/highlight_repository.py](../content_service/application/repositories/highlight_repository.py) | `HighlightRepository` |
| [application/repositories/interview_repository.py](../content_service/application/repositories/interview_repository.py) | `InterviewRepository` |
| [application/repositories/source_document_repository.py](../content_service/application/repositories/source_document_repository.py) | `SourceDocumentRepository` |
| [application/services/commands/article_command_service.py](../content_service/application/services/commands/article_command_service.py) | `ArticleCommandService` |
| [application/services/commands/extended_profile_command_service.py](../content_service/application/services/commands/extended_profile_command_service.py) | `ExtendedProfileCommandService` |
| [application/services/commands/highlight_command_service.py](../content_service/application/services/commands/highlight_command_service.py) | `HighlightCommandService` |
| [application/services/commands/interview_command_service.py](../content_service/application/services/commands/interview_command_service.py) | `InterviewCommandService` |
| [application/services/commands/source_document_command_service.py](../content_service/application/services/commands/source_document_command_service.py) | `SourceDocumentCommandService` |
| [application/services/queries/article_query_service.py](../content_service/application/services/queries/article_query_service.py) | `ArticleQueryService` |
| [application/services/queries/corpus_statistics_query_service.py](../content_service/application/services/queries/corpus_statistics_query_service.py) | `CorpusStatisticsQueryService` |
| [application/services/queries/extended_profile_query_service.py](../content_service/application/services/queries/extended_profile_query_service.py) | `ExtendedProfileQueryService` |
| [application/services/queries/highlight_query_service.py](../content_service/application/services/queries/highlight_query_service.py) | `HighlightQueryService` |
| [application/services/queries/interview_query_service.py](../content_service/application/services/queries/interview_query_service.py) | `InterviewQueryService` |
| [application/services/queries/source_document_query_service.py](../content_service/application/services/queries/source_document_query_service.py) | `SourceDocumentQueryService` |
| [bootstrap.py](../content_service/bootstrap.py) | `Container` |
| [domain/entities/article.py](../content_service/domain/entities/article.py) | `Article` |
| [domain/entities/extended_profile.py](../content_service/domain/entities/extended_profile.py) | `ExtendedProfile` |
| [domain/entities/highlight.py](../content_service/domain/entities/highlight.py) | `Highlight` |
| [domain/entities/interview.py](../content_service/domain/entities/interview.py) | `Interview` |
| [domain/entities/source_document.py](../content_service/domain/entities/source_document.py) | `SourceDocument` |
| [domain/exceptions.py](../content_service/domain/exceptions.py) | `DomainError`, `VersionConflict` |
| [domain/services/publication_policy.py](../content_service/domain/services/publication_policy.py) | `PublicationPolicy` |
| [infrastructure/database/corpus_statistics_adapter.py](../content_service/infrastructure/database/corpus_statistics_adapter.py) | `MongoCorpusStatisticsReader` |
| [infrastructure/database/mappers/source_document_persistence_mapper.py](../content_service/infrastructure/database/mappers/source_document_persistence_mapper.py) | `SourceDocumentPersistenceMapper` |
| [infrastructure/database/models/source_document_model.py](../content_service/infrastructure/database/models/source_document_model.py) | `SourceDocumentModel` |
| [infrastructure/database/repositories/mongo_article_repository.py](../content_service/infrastructure/database/repositories/mongo_article_repository.py) | `MongoArticleRepository` |
| [infrastructure/database/repositories/mongo_extended_profile_repository.py](../content_service/infrastructure/database/repositories/mongo_extended_profile_repository.py) | `MongoExtendedProfileRepository` |
| [infrastructure/database/repositories/mongo_highlight_repository.py](../content_service/infrastructure/database/repositories/mongo_highlight_repository.py) | `MongoHighlightRepository` |
| [infrastructure/database/repositories/mongo_interview_repository.py](../content_service/infrastructure/database/repositories/mongo_interview_repository.py) | `MongoInterviewRepository` |
| [infrastructure/database/repositories/mongo_source_document_repository.py](../content_service/infrastructure/database/repositories/mongo_source_document_repository.py) | `MongoSourceDocumentRepository` |
| [infrastructure/database/unit_of_work_adapter.py](../content_service/infrastructure/database/unit_of_work_adapter.py) | `MongoUnitOfWork` |
| [presentation/api/controllers/article_controller.py](../content_service/presentation/api/controllers/article_controller.py) | `ArticleController` |
| [presentation/api/controllers/corpus_statistics_query_service_controller.py](../content_service/presentation/api/controllers/corpus_statistics_query_service_controller.py) | `CorpusStatisticsQueryServiceController` |
| [presentation/api/controllers/extended_profile_controller.py](../content_service/presentation/api/controllers/extended_profile_controller.py) | `ExtendedProfileController` |
| [presentation/api/controllers/highlight_controller.py](../content_service/presentation/api/controllers/highlight_controller.py) | `HighlightController` |
| [presentation/api/controllers/interview_controller.py](../content_service/presentation/api/controllers/interview_controller.py) | `InterviewController` |
| [presentation/api/controllers/source_document_controller.py](../content_service/presentation/api/controllers/source_document_controller.py) | `SourceDocumentController` |
| [presentation/messaging/consumers/source_document_batch_consumer.py](../content_service/presentation/messaging/consumers/source_document_batch_consumer.py) | `SourceDocumentBatchConsumer` |
| [settings.py](../content_service/settings.py) | `Settings` |

## Analytics service

| Module | Declared classes |
| --- | --- |
| [application/dtos/comparison_query.py](../analytics_service/application/dtos/comparison_query.py) | `ComparisonQuery` |
| [application/dtos/recommendation_dto.py](../analytics_service/application/dtos/recommendation_dto.py) | `RecommendationDTO` |
| [application/dtos/relationship_dto.py](../analytics_service/application/dtos/relationship_dto.py) | `RelationshipDTO` |
| [application/dtos/team_comparison_dto.py](../analytics_service/application/dtos/team_comparison_dto.py) | `TeamComparisonDTO` |
| [application/ports/comparison_cache.py](../analytics_service/application/ports/comparison_cache.py) | `ComparisonCache` |
| [application/ports/graph_projection.py](../analytics_service/application/ports/graph_projection.py) | `GraphProjection` |
| [application/ports/relationship_reader.py](../analytics_service/application/ports/relationship_reader.py) | `RelationshipReader` |
| [application/ports/statistics_projection.py](../analytics_service/application/ports/statistics_projection.py) | `StatisticsProjection` |
| [application/ports/statistics_reader.py](../analytics_service/application/ports/statistics_reader.py) | `StatisticsReader` |
| [application/ports/unit_of_work.py](../analytics_service/application/ports/unit_of_work.py) | `UnitOfWork` |
| [application/repositories/crud_repository.py](../analytics_service/application/repositories/crud_repository.py) | `CrudRepository` |
| [application/services/commands/graph_projection_service.py](../analytics_service/application/services/commands/graph_projection_service.py) | `GraphProjectionService` |
| [application/services/commands/statistics_projection_service.py](../analytics_service/application/services/commands/statistics_projection_service.py) | `StatisticsProjectionService` |
| [application/services/queries/comparison_service.py](../analytics_service/application/services/queries/comparison_service.py) | `ComparisonService` |
| [application/services/queries/recommendation_service.py](../analytics_service/application/services/queries/recommendation_service.py) | `RecommendationService` |
| [application/services/queries/relationship_service.py](../analytics_service/application/services/queries/relationship_service.py) | `RelationshipService` |
| [bootstrap.py](../analytics_service/bootstrap.py) | `Container` |
| [domain/entities/player_connection.py](../analytics_service/domain/entities/player_connection.py) | `PlayerConnection` |
| [domain/entities/team_statistics.py](../analytics_service/domain/entities/team_statistics.py) | `TeamStatistics` |
| [domain/exceptions.py](../analytics_service/domain/exceptions.py) | `DomainError`, `VersionConflict` |
| [domain/services/statistics_calculator.py](../analytics_service/domain/services/statistics_calculator.py) | `StatisticsCalculator` |
| [infrastructure/cache/comparison_cache_adapter.py](../analytics_service/infrastructure/cache/comparison_cache_adapter.py) | `RedisComparisonCache` |
| [infrastructure/database/statistics_projection_adapter.py](../analytics_service/infrastructure/database/statistics_projection_adapter.py) | `PostgresStatisticsProjection` |
| [infrastructure/database/statistics_reader_adapter.py](../analytics_service/infrastructure/database/statistics_reader_adapter.py) | `PostgresStatisticsReader` |
| [infrastructure/database/unit_of_work_adapter.py](../analytics_service/infrastructure/database/unit_of_work_adapter.py) | `PostgresUnitOfWork` |
| [infrastructure/graph/graph_projection_adapter.py](../analytics_service/infrastructure/graph/graph_projection_adapter.py) | `Neo4jGraphProjection` |
| [infrastructure/graph/relationship_reader_adapter.py](../analytics_service/infrastructure/graph/relationship_reader_adapter.py) | `Neo4jRelationshipReader` |
| [presentation/api/controllers/comparison_service_controller.py](../analytics_service/presentation/api/controllers/comparison_service_controller.py) | `ComparisonServiceController` |
| [presentation/api/controllers/recommendation_service_controller.py](../analytics_service/presentation/api/controllers/recommendation_service_controller.py) | `RecommendationServiceController` |
| [presentation/api/controllers/relationship_service_controller.py](../analytics_service/presentation/api/controllers/relationship_service_controller.py) | `RelationshipServiceController` |
| [presentation/messaging/consumers/graph_event_consumer.py](../analytics_service/presentation/messaging/consumers/graph_event_consumer.py) | `GraphEventConsumer` |
| [presentation/messaging/consumers/statistics_event_consumer.py](../analytics_service/presentation/messaging/consumers/statistics_event_consumer.py) | `StatisticsEventConsumer` |
| [settings.py](../analytics_service/settings.py) | `Settings` |

## Search service

| Module | Declared classes |
| --- | --- |
| [application/dtos/search_history_dto.py](../search_service/application/dtos/search_history_dto.py) | `SearchHistoryDTO` |
| [application/dtos/search_hit_dto.py](../search_service/application/dtos/search_hit_dto.py) | `SearchHitDTO` |
| [application/dtos/search_query_dto.py](../search_service/application/dtos/search_query_dto.py) | `SearchQueryDTO` |
| [application/dtos/search_result_dto.py](../search_service/application/dtos/search_result_dto.py) | `SearchResultDTO` |
| [application/ports/search_cache.py](../search_service/application/ports/search_cache.py) | `SearchCache` |
| [application/ports/search_history.py](../search_service/application/ports/search_history.py) | `SearchHistory` |
| [application/ports/search_index.py](../search_service/application/ports/search_index.py) | `SearchIndex` |
| [application/ports/search_reader.py](../search_service/application/ports/search_reader.py) | `SearchReader` |
| [application/ports/unit_of_work.py](../search_service/application/ports/unit_of_work.py) | `UnitOfWork` |
| [application/repositories/crud_repository.py](../search_service/application/repositories/crud_repository.py) | `CrudRepository` |
| [application/services/commands/indexing_service.py](../search_service/application/services/commands/indexing_service.py) | `IndexingService` |
| [application/services/queries/search_service.py](../search_service/application/services/queries/search_service.py) | `SearchService` |
| [application/services/queries/search_statistics_query_service.py](../search_service/application/services/queries/search_statistics_query_service.py) | `SearchStatisticsQueryService` |
| [bootstrap.py](../search_service/bootstrap.py) | `Container` |
| [domain/entities/searchable_document.py](../search_service/domain/entities/searchable_document.py) | `SearchableDocument` |
| [domain/exceptions.py](../search_service/domain/exceptions.py) | `DomainError`, `VersionConflict` |
| [domain/services/query_normalization_policy.py](../search_service/domain/services/query_normalization_policy.py) | `QueryNormalizationPolicy` |
| [infrastructure/cache/search_cache_adapter.py](../search_service/infrastructure/cache/search_cache_adapter.py) | `RedisSearchCache` |
| [infrastructure/database/unit_of_work_adapter.py](../search_service/infrastructure/database/unit_of_work_adapter.py) | `PostgresUnitOfWork` |
| [infrastructure/search/search_history_adapter.py](../search_service/infrastructure/search/search_history_adapter.py) | `ElasticsearchHistory` |
| [infrastructure/search/search_index_adapter.py](../search_service/infrastructure/search/search_index_adapter.py) | `ElasticsearchIndex` |
| [infrastructure/search/search_reader_adapter.py](../search_service/infrastructure/search/search_reader_adapter.py) | `ElasticsearchReader` |
| [presentation/api/controllers/search_service_controller.py](../search_service/presentation/api/controllers/search_service_controller.py) | `SearchServiceController` |
| [presentation/api/controllers/search_statistics_query_service_controller.py](../search_service/presentation/api/controllers/search_statistics_query_service_controller.py) | `SearchStatisticsQueryServiceController` |
| [presentation/messaging/consumers/indexing_event_consumer.py](../search_service/presentation/messaging/consumers/indexing_event_consumer.py) | `IndexingEventConsumer` |
| [settings.py](../search_service/settings.py) | `Settings` |

## Identity service

| Module | Declared classes |
| --- | --- |
| [application/dtos/account_dto.py](../identity_service/application/dtos/account_dto.py) | `AccountDTO` |
| [application/dtos/bookmark_dto.py](../identity_service/application/dtos/bookmark_dto.py) | `BookmarkDTO` |
| [application/dtos/credential_dto.py](../identity_service/application/dtos/credential_dto.py) | `CredentialDTO` |
| [application/dtos/login_dto.py](../identity_service/application/dtos/login_dto.py) | `LoginDTO` |
| [application/dtos/registration_dto.py](../identity_service/application/dtos/registration_dto.py) | `RegistrationDTO` |
| [application/ports/credential_issuer.py](../identity_service/application/ports/credential_issuer.py) | `CredentialIssuer` |
| [application/ports/password_hasher.py](../identity_service/application/ports/password_hasher.py) | `PasswordHasher` |
| [application/ports/unit_of_work.py](../identity_service/application/ports/unit_of_work.py) | `UnitOfWork` |
| [application/repositories/bookmark_repository.py](../identity_service/application/repositories/bookmark_repository.py) | `BookmarkRepository` |
| [application/repositories/crud_repository.py](../identity_service/application/repositories/crud_repository.py) | `CrudRepository` |
| [application/repositories/user_repository.py](../identity_service/application/repositories/user_repository.py) | `UserRepository` |
| [application/services/commands/account_command_service.py](../identity_service/application/services/commands/account_command_service.py) | `AccountCommandService` |
| [application/services/commands/bookmark_command_service.py](../identity_service/application/services/commands/bookmark_command_service.py) | `BookmarkCommandService` |
| [application/services/queries/account_query_service.py](../identity_service/application/services/queries/account_query_service.py) | `AccountQueryService` |
| [application/services/queries/bookmark_query_service.py](../identity_service/application/services/queries/bookmark_query_service.py) | `BookmarkQueryService` |
| [bootstrap.py](../identity_service/bootstrap.py) | `Container` |
| [domain/entities/bookmark.py](../identity_service/domain/entities/bookmark.py) | `Bookmark` |
| [domain/entities/user.py](../identity_service/domain/entities/user.py) | `User` |
| [domain/exceptions.py](../identity_service/domain/exceptions.py) | `DomainError`, `VersionConflict` |
| [domain/services/bookmark_policy.py](../identity_service/domain/services/bookmark_policy.py) | `BookmarkPolicy` |
| [infrastructure/database/mappers/user_persistence_mapper.py](../identity_service/infrastructure/database/mappers/user_persistence_mapper.py) | `UserPersistenceMapper` |
| [infrastructure/database/models/user_model.py](../identity_service/infrastructure/database/models/user_model.py) | `UserModel` |
| [infrastructure/database/repositories/postgres_bookmark_repository.py](../identity_service/infrastructure/database/repositories/postgres_bookmark_repository.py) | `PostgresBookmarkRepository` |
| [infrastructure/database/repositories/postgres_user_repository.py](../identity_service/infrastructure/database/repositories/postgres_user_repository.py) | `PostgresUserRepository` |
| [infrastructure/database/unit_of_work_adapter.py](../identity_service/infrastructure/database/unit_of_work_adapter.py) | `PostgresUnitOfWork` |
| [infrastructure/security/credential_issuer_adapter.py](../identity_service/infrastructure/security/credential_issuer_adapter.py) | `CredentialIssuerAdapter` |
| [infrastructure/security/password_hasher_adapter.py](../identity_service/infrastructure/security/password_hasher_adapter.py) | `PasswordHashingAdapter` |
| [presentation/api/controllers/account_command_service_controller.py](../identity_service/presentation/api/controllers/account_command_service_controller.py) | `AccountCommandServiceController` |
| [presentation/api/controllers/account_query_service_controller.py](../identity_service/presentation/api/controllers/account_query_service_controller.py) | `AccountQueryServiceController` |
| [presentation/api/controllers/bookmark_command_service_controller.py](../identity_service/presentation/api/controllers/bookmark_command_service_controller.py) | `BookmarkCommandServiceController` |
| [presentation/api/controllers/bookmark_query_service_controller.py](../identity_service/presentation/api/controllers/bookmark_query_service_controller.py) | `BookmarkQueryServiceController` |
| [settings.py](../identity_service/settings.py) | `Settings` |

## Ingestion service

| Module | Declared classes |
| --- | --- |
| [application/dtos/job_progress_dto.py](../ingestion_service/application/dtos/job_progress_dto.py) | `JobProgressDTO` |
| [application/dtos/provider_metadata_dto.py](../ingestion_service/application/dtos/provider_metadata_dto.py) | `ProviderMetadataDTO` |
| [application/dtos/start_import_dto.py](../ingestion_service/application/dtos/start_import_dto.py) | `StartImportDTO` |
| [application/dtos/start_replay_dto.py](../ingestion_service/application/dtos/start_replay_dto.py) | `StartReplayDTO` |
| [application/ports/command_publisher.py](../ingestion_service/application/ports/command_publisher.py) | `CommandPublisher` |
| [application/ports/dataset_reader.py](../ingestion_service/application/ports/dataset_reader.py) | `DatasetReader` |
| [application/ports/metadata_provider.py](../ingestion_service/application/ports/metadata_provider.py) | `MetadataProvider` |
| [application/ports/rate_controller.py](../ingestion_service/application/ports/rate_controller.py) | `RateController` |
| [application/ports/unit_of_work.py](../ingestion_service/application/ports/unit_of_work.py) | `UnitOfWork` |
| [application/repositories/crud_repository.py](../ingestion_service/application/repositories/crud_repository.py) | `CrudRepository` |
| [application/repositories/enrichment_job_repository.py](../ingestion_service/application/repositories/enrichment_job_repository.py) | `EnrichmentJobRepository` |
| [application/repositories/identity_candidate_repository.py](../ingestion_service/application/repositories/identity_candidate_repository.py) | `IdentityCandidateRepository` |
| [application/repositories/import_job_repository.py](../ingestion_service/application/repositories/import_job_repository.py) | `ImportJobRepository` |
| [application/repositories/replay_job_repository.py](../ingestion_service/application/repositories/replay_job_repository.py) | `ReplayJobRepository` |
| [application/repositories/validation_issue_repository.py](../ingestion_service/application/repositories/validation_issue_repository.py) | `ValidationIssueRepository` |
| [application/services/commands/batch_completion_service.py](../ingestion_service/application/services/commands/batch_completion_service.py) | `BatchCompletionService` |
| [application/services/commands/enrichment_service.py](../ingestion_service/application/services/commands/enrichment_service.py) | `EnrichmentService` |
| [application/services/commands/import_review_service.py](../ingestion_service/application/services/commands/import_review_service.py) | `ImportReviewService` |
| [application/services/commands/import_service.py](../ingestion_service/application/services/commands/import_service.py) | `ImportService` |
| [application/services/commands/replay_command_service.py](../ingestion_service/application/services/commands/replay_command_service.py) | `ReplayCommandService` |
| [application/services/queries/import_query_service.py](../ingestion_service/application/services/queries/import_query_service.py) | `ImportQueryService` |
| [application/services/queries/replay_query_service.py](../ingestion_service/application/services/queries/replay_query_service.py) | `ReplayQueryService` |
| [bootstrap.py](../ingestion_service/bootstrap.py) | `Container` |
| [domain/entities/enrichment_job.py](../ingestion_service/domain/entities/enrichment_job.py) | `EnrichmentJob` |
| [domain/entities/identity_candidate.py](../ingestion_service/domain/entities/identity_candidate.py) | `IdentityCandidate` |
| [domain/entities/import_job.py](../ingestion_service/domain/entities/import_job.py) | `ImportJob` |
| [domain/entities/replay_job.py](../ingestion_service/domain/entities/replay_job.py) | `ReplayJob` |
| [domain/entities/validation_issue.py](../ingestion_service/domain/entities/validation_issue.py) | `ValidationIssue` |
| [domain/exceptions.py](../ingestion_service/domain/exceptions.py) | `DomainError`, `VersionConflict` |
| [domain/services/entity_resolver.py](../ingestion_service/domain/services/entity_resolver.py) | `EntityResolver` |
| [infrastructure/database/mappers/import_job_persistence_mapper.py](../ingestion_service/infrastructure/database/mappers/import_job_persistence_mapper.py) | `ImportJobPersistenceMapper` |
| [infrastructure/database/models/import_job_model.py](../ingestion_service/infrastructure/database/models/import_job_model.py) | `ImportJobModel` |
| [infrastructure/database/repositories/postgres_enrichment_job_repository.py](../ingestion_service/infrastructure/database/repositories/postgres_enrichment_job_repository.py) | `PostgresEnrichmentJobRepository` |
| [infrastructure/database/repositories/postgres_identity_candidate_repository.py](../ingestion_service/infrastructure/database/repositories/postgres_identity_candidate_repository.py) | `PostgresIdentityCandidateRepository` |
| [infrastructure/database/repositories/postgres_import_job_repository.py](../ingestion_service/infrastructure/database/repositories/postgres_import_job_repository.py) | `PostgresImportJobRepository` |
| [infrastructure/database/repositories/postgres_replay_job_repository.py](../ingestion_service/infrastructure/database/repositories/postgres_replay_job_repository.py) | `PostgresReplayJobRepository` |
| [infrastructure/database/repositories/postgres_validation_issue_repository.py](../ingestion_service/infrastructure/database/repositories/postgres_validation_issue_repository.py) | `PostgresValidationIssueRepository` |
| [infrastructure/database/unit_of_work_adapter.py](../ingestion_service/infrastructure/database/unit_of_work_adapter.py) | `PostgresUnitOfWork` |
| [infrastructure/datasets/dataset_reader_adapter.py](../ingestion_service/infrastructure/datasets/dataset_reader_adapter.py) | `KaggleAndTextFileReader` |
| [infrastructure/messaging/command_publisher_adapter.py](../ingestion_service/infrastructure/messaging/command_publisher_adapter.py) | `RabbitMQCommandPublisher` |
| [infrastructure/pacing/rate_controller_adapter.py](../ingestion_service/infrastructure/pacing/rate_controller_adapter.py) | `AsyncioRateController` |
| [infrastructure/providers/liquipedia_adapter.py](../ingestion_service/infrastructure/providers/liquipedia_adapter.py) | `LiquipediaAdapter` |
| [infrastructure/providers/pandascore_adapter.py](../ingestion_service/infrastructure/providers/pandascore_adapter.py) | `PandaScoreAdapter` |
| [presentation/api/controllers/enrichment_service_controller.py](../ingestion_service/presentation/api/controllers/enrichment_service_controller.py) | `EnrichmentServiceController` |
| [presentation/api/controllers/import_query_service_controller.py](../ingestion_service/presentation/api/controllers/import_query_service_controller.py) | `ImportQueryServiceController` |
| [presentation/api/controllers/import_review_service_controller.py](../ingestion_service/presentation/api/controllers/import_review_service_controller.py) | `ImportReviewServiceController` |
| [presentation/api/controllers/import_service_controller.py](../ingestion_service/presentation/api/controllers/import_service_controller.py) | `ImportServiceController` |
| [presentation/api/controllers/replay_command_service_controller.py](../ingestion_service/presentation/api/controllers/replay_command_service_controller.py) | `ReplayCommandServiceController` |
| [presentation/api/controllers/replay_query_service_controller.py](../ingestion_service/presentation/api/controllers/replay_query_service_controller.py) | `ReplayQueryServiceController` |
| [presentation/messaging/consumers/batch_completed_consumer.py](../ingestion_service/presentation/messaging/consumers/batch_completed_consumer.py) | `BatchCompletedConsumer` |
| [settings.py](../ingestion_service/settings.py) | `Settings` |

## Contracts

| Module | Declared classes |
| --- | --- |
| [messages.py](../contracts/messages.py) | `MessageHeaders`, `ChangeNotification`, `BatchCompleted`, `SourceDocumentRecord`, `StoreSourceDocumentBatch`, `PlayerStatRecord`, `MatchRecord`, `ImportMatchBatch`, `ScheduleJob` |
