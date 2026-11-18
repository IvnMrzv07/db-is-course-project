from contextlib import asynccontextmanager
from uuid import UUID
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from content_service.runtime import build_runtime
from content_service.application.dtos.document_query import DocumentQuery

@asynccontextmanager
async def lifespan(app):
    client, repository, controller, commands = await build_runtime()
    app.state.controller = controller
    app.state.client = client
    yield
    await client.close()

app = FastAPI(title='Content API', lifespan=lifespan)

@app.exception_handler(PyMongoError)
async def database_error(request, exc):
    return JSONResponse(status_code=503, content={'detail': 'Document database unavailable or query timed out'})

@app.get('/health')
async def health():
    await app.state.client.admin.command('ping')
    return {'status': 'ok'}

@app.get('/api/v1/documents')
async def documents(q: str = Query('', max_length=200), document_type: str | None = None,
                    tournament: str | None = None, team: str | None = None,
                    date_from: str | None = None, date_to: str | None = None,
                    page: int = Query(1, ge=1, le=10000), page_size: int = Query(20, ge=1, le=100)):
    try:
        query = DocumentQuery(q=q, document_type=document_type, tournament=tournament, team=team,
                              date_from=date_from, date_to=date_to, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return await app.state.controller.list(query)

@app.get('/api/v1/documents/{document_id}')
async def document(document_id: UUID):
    result = await app.state.controller.get(document_id)
    if result is None:
        raise HTTPException(404, 'Document not found')
    return result

@app.get('/api/v1/corpus/statistics')
async def statistics():
    return await app.state.controller.statistics()
