from dataclasses import dataclass
import logging
from uuid import UUID
from content_service.application.ports.corpus_store import CorpusStore

@dataclass
class CorpusCommandService:
    repository: CorpusStore

    async def store(self, batch: dict):
        UUID(batch['batch_id'])
        UUID(batch['job_id'])
        if not 1 <= len(batch['documents']) <= 100:
            raise ValueError('Invalid batch size')
        for document in batch['documents']:
            UUID(document['id'])
            if document['corpus_scope'] != 'kaggle-cs' or document['publication_status'] != 'published':
                raise ValueError('Unsupported corpus or publication state')
            if not document['title'] or not document['text'] or document['version'] != 1:
                raise ValueError('Invalid document')
        result = await self.repository.persist_batch(batch)
        logging.getLogger(__name__).info('Committed batch=%s inserted=%s duplicates=%s', batch['batch_id'], result['inserted'], result['duplicates'])
        return result
