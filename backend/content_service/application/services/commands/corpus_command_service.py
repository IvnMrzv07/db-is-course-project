from dataclasses import dataclass
import logging
from uuid import UUID
from content_service.application.ports.corpus_store import CorpusStore

# Corpus scope -> required is_synthetic flag; generated load data never enters the factual scope (D38).
CORPUS_SCOPES = {'kaggle-cs': False, 'synthetic-cs': True}

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
            if document['corpus_scope'] not in CORPUS_SCOPES or document['publication_status'] != 'published':
                raise ValueError('Unsupported corpus or publication state')
            if document['is_synthetic'] is not CORPUS_SCOPES[document['corpus_scope']]:
                raise ValueError('Synthetic flag does not match corpus scope')
            if not document['title'] or not document['text'] or document['version'] != 1:
                raise ValueError('Invalid document')
        result = await self.repository.persist_batch(batch)
        logging.getLogger(__name__).info('Committed batch=%s inserted=%s duplicates=%s', batch['batch_id'], result['inserted'], result['duplicates'])
        return result
