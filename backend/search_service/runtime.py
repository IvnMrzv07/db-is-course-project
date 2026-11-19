"""Live composition root of the search slice (Elasticsearch + RabbitMQ); bootstrap.py stays connection-free."""
import os

from search_service.application.services.commands.document_indexing_service import DocumentIndexingService
from search_service.application.services.queries.full_text_search_service import FullTextSearchService
from search_service.infrastructure.search.elasticsearch_documents import ElasticsearchDocumentIndex
from search_service.presentation.api.controllers.full_text_search_controller import FullTextSearchController
from search_service.presentation.messaging.consumers.document_index_consumer import DocumentIndexConsumer


def build_index() -> ElasticsearchDocumentIndex:
    return ElasticsearchDocumentIndex(url=os.environ.get('SEARCH_URL', 'http://localhost:9200'),
                                      timeout_seconds=float(os.environ.get('SEARCH_TIMEOUT_SECONDS', '5')))


def build_api(index: ElasticsearchDocumentIndex) -> FullTextSearchController:
    return FullTextSearchController(service=FullTextSearchService(index=index))


def build_consumer(index: ElasticsearchDocumentIndex) -> DocumentIndexConsumer:
    return DocumentIndexConsumer(service=DocumentIndexingService(index=index))
