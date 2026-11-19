"""Search API: `GET /api/v1/search` (full-text, Elasticsearch) and `GET /api/v1/search/status`.

States: 200 + status=found|empty (degraded=true for a partial engine answer), 422 invalid request,
503 status=degraded when Elasticsearch is unavailable, 500 status=error for anything unexpected.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from search_service.application.dtos.full_text_query import FullTextQuery
from search_service.application.ports.document_index import SearchBackendUnavailable
from search_service.runtime import build_api, build_index

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    index = build_index()  # no connection is opened here: the API starts even while ES is down
    app.state.controller = build_api(index)
    yield
    await index.close()


app = FastAPI(title='Search API', lifespan=lifespan)


@app.exception_handler(SearchBackendUnavailable)
async def search_unavailable(request, exc):
    log.warning('Search degraded: %s', exc)
    return JSONResponse(status_code=503, content={
        'status': 'degraded', 'detail': 'Пошуковий індекс тимчасово недоступний', 'reason': str(exc)})


@app.exception_handler(Exception)
async def search_error(request, exc):
    log.exception('Search request failed')
    return JSONResponse(status_code=500, content={'status': 'error', 'detail': 'Помилка пошукового сервісу'})


@app.get('/health')
async def health():
    return {'status': 'ok'}


@app.get('/api/v1/search/status')
async def status():
    return await app.state.controller.status()


@app.get('/api/v1/search')
async def search(q: str = Query('', max_length=200), mode: str = Query('all', max_length=16),
                 corpus_scope: str = Query('all', max_length=32),
                 document_type: str | None = Query(None, max_length=16),
                 map_name: str | None = Query(None, max_length=64),
                 include_synthetic: bool = True,
                 page: int = Query(1, ge=1, le=10000), page_size: int = Query(20, ge=1, le=50)):
    try:
        query = FullTextQuery(q=q, mode=mode, corpus_scope=corpus_scope, document_type=document_type or None,
                              map_name=map_name or None, include_synthetic=include_synthetic,
                              page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return await app.state.controller.search(query)
