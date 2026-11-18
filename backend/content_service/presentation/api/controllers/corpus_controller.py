from dataclasses import dataclass
from uuid import UUID
from content_service.application.services.queries.corpus_query_service import CorpusQueryService
from content_service.application.dtos.document_query import DocumentQuery

@dataclass
class CorpusController:
    queries: CorpusQueryService

    async def list(self, query: DocumentQuery):
        return await self.queries.browse(query)

    async def get(self, document_id: UUID):
        return await self.queries.get(document_id)

    async def statistics(self):
        return await self.queries.statistics()
