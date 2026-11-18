from __future__ import annotations

from dataclasses import dataclass
from competition_service.settings import Settings
from competition_service.infrastructure.database.unit_of_work_adapter import PostgresUnitOfWork
from competition_service.infrastructure.database.repositories.postgres_player_repository import PostgresPlayerRepository
from competition_service.application.services.commands.player_command_service import PlayerCommandService
from competition_service.application.services.queries.player_query_service import PlayerQueryService
from competition_service.presentation.api.controllers.player_controller import PlayerController
from competition_service.infrastructure.database.repositories.postgres_team_repository import PostgresTeamRepository
from competition_service.application.services.commands.team_command_service import TeamCommandService
from competition_service.application.services.queries.team_query_service import TeamQueryService
from competition_service.presentation.api.controllers.team_controller import TeamController
from competition_service.infrastructure.database.repositories.postgres_tournament_repository import PostgresTournamentRepository
from competition_service.application.services.commands.tournament_command_service import TournamentCommandService
from competition_service.application.services.queries.tournament_query_service import TournamentQueryService
from competition_service.presentation.api.controllers.tournament_controller import TournamentController
from competition_service.infrastructure.database.repositories.postgres_match_repository import PostgresMatchRepository
from competition_service.application.services.commands.match_command_service import MatchCommandService
from competition_service.application.services.queries.match_query_service import MatchQueryService
from competition_service.presentation.api.controllers.match_controller import MatchController
from competition_service.infrastructure.database.repositories.postgres_map_result_repository import PostgresMapResultRepository
from competition_service.infrastructure.database.repositories.postgres_player_map_stats_repository import PostgresPlayerMapStatsRepository
from competition_service.infrastructure.database.repositories.postgres_match_lineup_repository import PostgresMatchLineupRepository
from competition_service.infrastructure.database.repositories.postgres_team_membership_repository import PostgresTeamMembershipRepository
from competition_service.infrastructure.database.repositories.postgres_external_identity_repository import PostgresExternalIdentityRepository
from competition_service.application.services.commands.import_match_service import ImportMatchService
from competition_service.presentation.messaging.consumers.import_match_consumer import ImportMatchConsumer


@dataclass(kw_only=True)
class Container:
    """Inspectable object graph; not a running application."""

    player_controller: PlayerController
    team_controller: TeamController
    tournament_controller: TournamentController
    match_controller: MatchController
    import_consumer: ImportMatchConsumer


def build_container(settings: Settings) -> Container:
    """Wire stub adapters without connecting to any external system.

    Create request/job-scoped units of work when implementing runtime lifecycles.
    Empty connection strings are placeholders here, not valid deployment defaults.
    """
    uow = PostgresUnitOfWork(connection_url=settings.database_url or "")
    player_repo = PostgresPlayerRepository(connection_url=settings.database_url or "")
    player_commands = PlayerCommandService(repository=player_repo, unit_of_work=uow)
    player_queries = PlayerQueryService(repository=player_repo)
    player_controller = PlayerController(commands=player_commands, queries=player_queries)
    team_repo = PostgresTeamRepository(connection_url=settings.database_url or "")
    team_commands = TeamCommandService(repository=team_repo, unit_of_work=uow)
    team_queries = TeamQueryService(repository=team_repo)
    team_controller = TeamController(commands=team_commands, queries=team_queries)
    tournament_repo = PostgresTournamentRepository(connection_url=settings.database_url or "")
    tournament_commands = TournamentCommandService(repository=tournament_repo, unit_of_work=uow)
    tournament_queries = TournamentQueryService(repository=tournament_repo)
    tournament_controller = TournamentController(commands=tournament_commands, queries=tournament_queries)
    match_repo = PostgresMatchRepository(connection_url=settings.database_url or "")
    match_commands = MatchCommandService(repository=match_repo, unit_of_work=uow)
    match_queries = MatchQueryService(repository=match_repo)
    match_controller = MatchController(commands=match_commands, queries=match_queries)
    map_result_repo = PostgresMapResultRepository(connection_url=settings.database_url or "")
    player_map_stats_repo = PostgresPlayerMapStatsRepository(connection_url=settings.database_url or "")
    match_lineup_repo = PostgresMatchLineupRepository(connection_url=settings.database_url or "")
    team_membership_repo = PostgresTeamMembershipRepository(connection_url=settings.database_url or "")
    external_identity_repo = PostgresExternalIdentityRepository(connection_url=settings.database_url or "")
    import_service = ImportMatchService(repository=match_repo, unit_of_work=uow)
    import_consumer = ImportMatchConsumer(service=import_service)
    return Container(
        player_controller=player_controller,
        team_controller=team_controller,
        tournament_controller=tournament_controller,
        match_controller=match_controller,
        import_consumer=import_consumer,
    )
