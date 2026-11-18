from dataclasses import dataclass
from uuid import UUID
from content_service.application.ports.corpus_store import CorpusStore
from content_service.application.dtos.document_query import DocumentQuery

@dataclass
class CorpusQueryService:
    repository: CorpusStore

    async def browse(self, query: DocumentQuery):
        return await self.repository.browse(query)

    async def get(self, document_id: UUID):
        return await self.repository.read(document_id)

    async def statistics(self):
        return await self.repository.statistics()
