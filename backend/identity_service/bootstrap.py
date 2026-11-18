from __future__ import annotations

from dataclasses import dataclass
from identity_service.settings import Settings
from identity_service.infrastructure.database.unit_of_work_adapter import PostgresUnitOfWork
from identity_service.infrastructure.database.repositories.postgres_user_repository import PostgresUserRepository
from identity_service.infrastructure.database.repositories.postgres_bookmark_repository import PostgresBookmarkRepository
from identity_service.infrastructure.security.password_hasher_adapter import PasswordHashingAdapter
from identity_service.infrastructure.security.credential_issuer_adapter import CredentialIssuerAdapter
from identity_service.application.services.commands.account_command_service import AccountCommandService
from identity_service.presentation.api.controllers.account_command_service_controller import AccountCommandServiceController
from identity_service.application.services.queries.account_query_service import AccountQueryService
from identity_service.presentation.api.controllers.account_query_service_controller import AccountQueryServiceController
from identity_service.application.services.commands.bookmark_command_service import BookmarkCommandService
from identity_service.presentation.api.controllers.bookmark_command_service_controller import BookmarkCommandServiceController
from identity_service.application.services.queries.bookmark_query_service import BookmarkQueryService
from identity_service.presentation.api.controllers.bookmark_query_service_controller import BookmarkQueryServiceController


@dataclass(kw_only=True)
class Container:
    """Inspectable object graph; not a running application."""

    account_command_service_controller: AccountCommandServiceController
    account_query_service_controller: AccountQueryServiceController
    bookmark_command_service_controller: BookmarkCommandServiceController
    bookmark_query_service_controller: BookmarkQueryServiceController


def build_container(settings: Settings) -> Container:
    """Wire stub adapters without connecting to any external system.

    Create request/job-scoped units of work when implementing runtime lifecycles.
    Empty connection strings are placeholders here, not valid deployment defaults.
    """
    uow = PostgresUnitOfWork(connection_url=settings.database_url or "")
    user_repo = PostgresUserRepository(connection_url=settings.database_url or "")
    bookmark_repo = PostgresBookmarkRepository(connection_url=settings.database_url or "")
    hasher = PasswordHashingAdapter(connection_url=settings.database_url or "")
    credentials = CredentialIssuerAdapter(connection_url=settings.database_url or "")
    account_command_service = AccountCommandService(users=user_repo, hasher=hasher, credentials=credentials, unit_of_work=uow)
    account_command_service_controller = AccountCommandServiceController(service=account_command_service)
    account_query_service = AccountQueryService(users=user_repo)
    account_query_service_controller = AccountQueryServiceController(service=account_query_service)
    bookmark_command_service = BookmarkCommandService(bookmarks=bookmark_repo, unit_of_work=uow)
    bookmark_command_service_controller = BookmarkCommandServiceController(service=bookmark_command_service)
    bookmark_query_service = BookmarkQueryService(bookmarks=bookmark_repo)
    bookmark_query_service_controller = BookmarkQueryServiceController(service=bookmark_query_service)
    return Container(
        account_command_service_controller=account_command_service_controller,
        account_query_service_controller=account_query_service_controller,
        bookmark_command_service_controller=bookmark_command_service_controller,
        bookmark_query_service_controller=bookmark_query_service_controller,
    )
