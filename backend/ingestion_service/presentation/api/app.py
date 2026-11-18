import os
import secrets
from contextlib import asynccontextmanager
from uuid import UUID
import asyncpg
from fastapi import FastAPI, Header, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from ingestion_service.runtime import build_runtime
from ingestion_service.infrastructure.database.replay_store import Conflict

@asynccontextmanager
async def lifespan(app):
    if len(os.environ.get('OPERATOR_TOKEN','')) < 24:
        raise RuntimeError('OPERATOR_TOKEN must contain at least 24 characters')
    pool, store, controller = await build_runtime()
    app.state.pool, app.state.controller = pool, controller
    yield
    await pool.close()

app = FastAPI(title='Ingestion API', lifespan=lifespan)

async def operator(authorization: str = Header('')):
    expected = 'Bearer ' + os.environ.get('OPERATOR_TOKEN','')
    if not os.environ.get('OPERATOR_TOKEN') or not secrets.compare_digest(authorization.encode(),expected.encode()):
        raise HTTPException(401,'Operator token required',headers={'WWW-Authenticate':'Bearer'})

@app.exception_handler(Conflict)
async def conflict(request, exc):
    return JSONResponse(status_code=409,content={'detail':str(exc)})

@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse(status_code=422,content={'detail':str(exc)})

@app.exception_handler(LookupError)
async def missing(request, exc):
    return JSONResponse(status_code=404,content={'detail':str(exc)})

@app.exception_handler(asyncpg.PostgresError)
@app.exception_handler(asyncpg.InterfaceError)
@app.exception_handler(TimeoutError)
@app.exception_handler(OSError)
async def unavailable(request, exc):
    return JSONResponse(status_code=503,content={'detail':'Import database unavailable'})

class StartBody(BaseModel):
    snapshot_id: str = 'kaggle-cs'
    target_rate: int = Field(100,ge=10,le=5000)

class RateBody(BaseModel):
    target_rate: int = Field(ge=10,le=5000)

@app.get('/health')
async def health():
    await app.state.pool.fetchval('SELECT 1')
    return {'status':'ok'}

@app.get('/api/v1/snapshots',dependencies=[Depends(operator)])
async def snapshots():
    return await app.state.controller.snapshots()

@app.post('/api/v1/replays',status_code=202,dependencies=[Depends(operator)])
async def start(body: StartBody,idempotency_key: str = Header(...,min_length=1,max_length=128)):
    return await app.state.controller.start(body.snapshot_id,body.target_rate,idempotency_key)

@app.get('/api/v1/replays',dependencies=[Depends(operator)])
async def jobs(page: int = Query(1,ge=1),page_size: int = Query(20,ge=1,le=100)):
    return await app.state.controller.list(page,page_size)

@app.get('/api/v1/replays/{job_id}',dependencies=[Depends(operator)])
async def job(job_id: UUID):
    result = await app.state.controller.get(str(job_id))
    if result is None:
        raise HTTPException(404,'Job not found')
    return result

@app.patch('/api/v1/replays/{job_id}/rate',dependencies=[Depends(operator)])
async def rate(job_id: UUID,body: RateBody):
    return await app.state.controller.change(str(job_id),'rate',body.target_rate)

@app.post('/api/v1/replays/{job_id}/pause',dependencies=[Depends(operator)])
async def pause(job_id: UUID):
    return await app.state.controller.change(str(job_id),'pause')

@app.post('/api/v1/replays/{job_id}/resume',dependencies=[Depends(operator)])
async def resume(job_id: UUID):
    return await app.state.controller.change(str(job_id),'resume')
