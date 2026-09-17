from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Self
from uuid import UUID
from contracts.messages import ChangeNotification, OutboxMessage
from search_service.application.ports.unit_of_work import UnitOfWork


@dataclass(kw_only=True)
class PostgresUnitOfWork(UnitOfWork):
    """Transaction adapter stub. Bootstrap opens no connections.

    Runtime implementation must bind injected repositories to a request/job-scoped
    session; this object cannot be shared as a mutable transaction across requests.
    """

    connection_url: str

    async def __aenter__(self) -> Self:
        raise NotImplementedError("Begin scoped transaction and bind repositories")

    async def __aexit__(self, exc_type: type[BaseException] | None,
                        exc: BaseException | None, traceback: TracebackType | None) -> None:
        raise NotImplementedError("Rollback unless committed; release session")

    async def add_event(self, event: ChangeNotification) -> None:
        raise NotImplementedError("Stage outbox change event in current transaction")

    async def add_message(self, message: OutboxMessage) -> None:
        raise NotImplementedError("Stage durable command, event, or completion")

    async def has_receipt(self, message_id: UUID) -> bool:
        raise NotImplementedError("Check transactional idempotency receipt")

    async def record_receipt(self, message_id: UUID) -> None:
        raise NotImplementedError("Record idempotency receipt with business changes")

    async def commit(self) -> None:
        raise NotImplementedError("Commit writes, receipts, and outbox atomically")

    async def rollback(self) -> None:
        raise NotImplementedError("Rollback local transaction")
