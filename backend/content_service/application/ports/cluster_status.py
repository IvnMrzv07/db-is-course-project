from typing import Protocol


class ClusterStatus(Protocol):
    async def status(self) -> dict: ...
