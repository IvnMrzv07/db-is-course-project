import asyncio
import copy
import json
import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from ingestion_service.infrastructure.datasets.prepare_corpus import convert, prepare
from content_service.application.dtos.document_query import DocumentQuery
from content_service.application.services.commands.corpus_command_service import CorpusCommandService
from content_service.application.services.queries.corpus_query_service import CorpusQueryService
from content_service.presentation.api.controllers.corpus_controller import CorpusController
from content_service.infrastructure.database.corpus_repository import mongo_filter, MongoCorpusRepository
from content_service.presentation.api.app import app as content_app
from ingestion_service.presentation.api.app import app as ingestion_app
from ingestion_service.application.services.commands.replay_operations import ReplayOperations


def row(**changes):
    return {**dict(match_id='1',game_id='2',is_total='False',team1='Alpha',team2='Beta',
        tournament='Cup',datetime='2024-02-29 12:00:00',map_name='Dust2',score1_game='13.0',score2_game='7.0'),**changes}


def test_conversion_stable_ids_and_no_invented_values():
    first=convert(row(),'digest')
    assert first==convert(row(),'digest')
    assert first['id']!=convert(row(is_total='True'),'digest')['id']
    assert 'Map score: 13-7' in first['text']
    assert first['related_entity_ids']==[]
    assert first['metadata']['source_timezone']=='unspecified'
    assert 'score:' not in convert(row(score1_game=''),'digest')['text']

@pytest.mark.parametrize('changes',[{'match_id':''},{'team1':''},{'datetime':'invalid'},{'is_total':'maybe'},{'game_id':''},{'score1_game':'nan'}])
def test_invalid_source_record(changes):
    with pytest.raises(ValueError):
        convert(row(**changes),'digest')


def test_full_archive_reproducible(tmp_path):
    archive=Path(__file__).resolve().parents[1]/'counter-strike-pro-matches.zip'
    manifest=prepare(archive,tmp_path)
    assert manifest['accepted']==20675
    assert manifest['rejected']==1
    assert manifest['issues']==[{'line':20100,'reason':'Missing team1'}]
    assert prepare(archive,tmp_path)==manifest
    records=[json.loads(line) for line in (tmp_path/'kaggle-cs.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len({d['id'] for d in records})==20675
    assert {d['metadata']['document_type'] for d in records}=={'series','map'}


def test_literal_search_and_combined_filters():
    query=DocumentQuery(q='.*[Alpha]',team='Alpha',document_type='map',date_from='2024-02-01',date_to='2024-02-29')
    where=mongo_filter(query)
    pattern=where['$and'][0]['$or'][0]['title']['$regex']
    assert re.search(pattern,'literal .*[Alpha]')
    assert not re.search(pattern,'unrelated Alpha')
    assert where['metadata.played_at']=={'$gte':'2024-02-01','$lt':'2024-03-01'}
    assert where['publication_status']=='published'
    assert len(where['$and'])==2

@pytest.mark.parametrize('arguments',[{'page':0},{'page_size':101},{'q':'x'*201},{'date_from':'2025-02-30'},
    {'date_from':'2025-02-02','date_to':'2025-02-01'},{'date_to':'9999-12-31'},{'document_type':'other'}])
def test_query_validation(arguments):
    with pytest.raises(ValueError):
        DocumentQuery(**arguments)


def test_http_controller_service_repository_flow():
    store=SimpleNamespace(browse=AsyncMock(return_value={'items':[],'total':0,'page':1,'page_size':20}),read=AsyncMock(return_value=None))
    content_app.state.controller=CorpusController(CorpusQueryService(store))
    client=TestClient(content_app)
    assert client.get('/api/v1/documents?q=Alpha&team=Beta').json()['items']==[]
    assert store.browse.call_args.args[0].team=='Beta'
    assert client.get('/api/v1/documents/'+str(uuid4())).status_code==404
    assert client.get('/api/v1/documents/invalid').status_code==422
    assert client.get('/api/v1/documents?page_size=101').status_code==422
    assert client.get('/api/v1/documents?date_from=wrong').status_code==422


def test_mongo_error_becomes_service_unavailable():
    from pymongo.errors import ServerSelectionTimeoutError
    store=SimpleNamespace(browse=AsyncMock(side_effect=ServerSelectionTimeoutError('offline')))
    content_app.state.controller=CorpusController(CorpusQueryService(store))
    assert TestClient(content_app).get('/api/v1/documents').status_code==503


def test_operator_auth_and_rate_bounds(monkeypatch):
    monkeypatch.setenv('OPERATOR_TOKEN','x'*32)
    ingestion_app.state.controller=SimpleNamespace(start=AsyncMock(return_value={'id':str(uuid4())}))
    client=TestClient(ingestion_app)
    assert client.post('/api/v1/replays',json={}).status_code==401
    headers={'Authorization':'Bearer '+'x'*32,'Idempotency-Key':'test'}
    assert client.post('/api/v1/replays',headers=headers,json={'target_rate':9}).status_code==422
    assert client.post('/api/v1/replays',headers=headers,json={'target_rate':5001}).status_code==422
    assert client.post('/api/v1/replays',headers=headers,json={}).status_code==202


def test_command_validation_precedes_database():
    store=SimpleNamespace(create_job=AsyncMock())
    commands=ReplayOperations(store)
    with pytest.raises(ValueError):
        asyncio.run(commands.start('kaggle-cs',1,'key'))
    store.create_job.assert_not_called()


# Transaction contract double: real Mongo integration is separately gated below.
class Collection:
    def __init__(self):
        self.rows={}
        self.fail=False
    async def find_one(self,where,*args,**kwargs):
        return copy.deepcopy(self.rows.get(where['_id']))
    async def update_one(self,where,update,upsert=False,**kwargs):
        key=where['_id']; inserted=key not in self.rows
        if inserted and upsert:
            self.rows[key]={'_id':key,**copy.deepcopy(update.get('$setOnInsert',{}))}
        if key in self.rows:
            for field,value in update.get('$inc',{}).items():
                self.rows[key][field]=self.rows[key].get(field,0)+value
        return SimpleNamespace(upserted_id=key if inserted and upsert else None)
    async def insert_one(self,document,**kwargs):
        if self.fail:
            raise RuntimeError('Injected outbox failure')
        self.rows[document['_id']]=copy.deepcopy(document)

class Session:
    def __init__(self,db): self.db=db
    async def __aenter__(self): return self
    async def __aexit__(self,*args): pass
    async def with_transaction(self,callback,**kwargs):
        previous={key:copy.deepcopy(value.rows) for key,value in vars(self.db).items() if isinstance(value,Collection)}
        try: return await callback(self)
        except Exception:
            for key,rows in previous.items(): getattr(self.db,key).rows=rows
            raise

class Database:
    def __init__(self):
        for name in ('source_documents','committed_batches','corpus_counters','outbox'):
            setattr(self,name,Collection())
        self.corpus_counters.rows['kaggle-cs']={'stored_documents':0}
        self.client=SimpleNamespace(start_session=lambda:Session(self))


def batch():
    return {'job_id':str(uuid4()),'batch_id':str(uuid4()),'checkpoint':1,'prepared_at':'2026-01-01T00:00:00+00:00',
        'documents':[convert(row(),'digest')]}


def test_batch_idempotency_and_new_job_duplicates():
    async def scenario():
        db=Database();service=CorpusCommandService(MongoCorpusRepository(db));command=batch()
        first=await service.store(command)
        assert first['inserted']==1
        assert await service.store(command)==first
        repeated={**command,'batch_id':str(uuid4()),'job_id':str(uuid4())}
        result=await service.store(repeated)
        assert result['inserted']==0 and result['duplicates']==1
        assert db.corpus_counters.rows['kaggle-cs']['stored_documents']==1
        assert len(db.outbox.rows)==2
    asyncio.run(scenario())


def test_batch_rollback_if_outbox_write_fails():
    async def scenario():
        db=Database();db.outbox.fail=True
        service=CorpusCommandService(MongoCorpusRepository(db))
        with pytest.raises(RuntimeError): await service.store(batch())
        assert db.source_documents.rows=={}
        assert db.committed_batches.rows=={}
        assert db.corpus_counters.rows['kaggle-cs']['stored_documents']==0
    asyncio.run(scenario())


def test_reject_replacing_immutable_snapshot():
    async def scenario():
        db=Database();service=CorpusCommandService(MongoCorpusRepository(db));command=batch()
        await service.store(command)
        command['batch_id']=str(uuid4())
        command['documents'][0]['metadata']['snapshot_sha256']='changed'
        with pytest.raises(ValueError): await service.store(command)
        assert db.corpus_counters.rows['kaggle-cs']['stored_documents']==1
    asyncio.run(scenario())
