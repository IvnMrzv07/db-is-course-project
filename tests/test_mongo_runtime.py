"""Opt-in real MongoDB transaction tests; needs a replica set, never production data."""
import asyncio
import copy
import os
from uuid import uuid4, UUID
import pytest
from pymongo import AsyncMongoClient
from content_service.infrastructure.database.corpus_repository import MongoCorpusRepository
from content_service.application.services.commands.corpus_command_service import CorpusCommandService
from content_service.application.dtos.document_query import DocumentQuery
from ingestion_service.infrastructure.datasets.prepare_corpus import convert

pytestmark=pytest.mark.skipif(not os.getenv('TEST_MONGO_URL'),reason='Requires isolated MongoDB replica set')

def test_real_mongo_transactions_queries_idempotency_and_rollback():
    async def scenario():
        client=AsyncMongoClient(os.environ['TEST_MONGO_URL'],serverSelectionTimeoutMS=5000,tz_aware=True)
        database=client['test_'+uuid4().hex]
        try:
            repo=MongoCorpusRepository(database);await repo.initialize();commands=CorpusCommandService(repo)
            source={'match_id':'1','game_id':'2','is_total':'False','team1':'Alpha.*','team2':'Beta',
                'tournament':'Cup','datetime':'2024-02-29 12:00:00','map_name':'Dust2','score1_game':'13','score2_game':'7'}
            document=convert(source,'test-digest')
            batch={'job_id':str(uuid4()),'batch_id':str(uuid4()),'checkpoint':1,'prepared_at':'2026-01-01T00:00:00+00:00','documents':[document]}
            first=await commands.store(batch);assert first['inserted']==1
            assert await commands.store(batch)==first
            again=await commands.store({**batch,'batch_id':str(uuid4())});assert again['duplicates']==1
            assert (await repo.statistics())['stored_documents']==1
            assert await database.source_documents.count_documents({})==1
            assert (await repo.browse(DocumentQuery(q='ALPHA.*',team='Beta',date_to='2024-02-29')))['total']==1
            assert (await repo.browse(DocumentQuery(q='Alpha....')))['total']==0
            assert (await repo.browse(DocumentQuery(page=2)))['items']==[]
            assert (await repo.read(UUID(document['id'])))['text']==document['text']
            assert await repo.read(uuid4()) is None
            # Insert a new document, then force a snapshot mismatch later in the same transaction.
            new=convert({**source,'match_id':'9'},'test-digest')
            changed={**document,'metadata':{**document['metadata'],'snapshot_sha256':'different'}}
            with pytest.raises(ValueError):await commands.store({**batch,'batch_id':str(uuid4()),'checkpoint':3,'documents':[new,changed]})
            assert await database.source_documents.count_documents({})==1
            assert await database.committed_batches.count_documents({})==2
            assert await database.outbox.count_documents({'sent':False})==2
        finally:
            await client.drop_database(database.name)
            await client.close()
    asyncio.run(scenario())


def test_concurrent_batches_lose_and_duplicate_nothing():
    """Overlapping batches on parallel writers: documents, counter slots and receipts stay consistent."""
    async def scenario():
        client=AsyncMongoClient(os.environ['TEST_MONGO_URL'],serverSelectionTimeoutMS=5000,tz_aware=True)
        database=client['test_'+uuid4().hex]
        try:
            repo=MongoCorpusRepository(database);await repo.initialize();commands=CorpusCommandService(repo)
            base={'game_id':'2','is_total':'False','team1':'Alpha','team2':'Beta','tournament':'Cup',
                'datetime':'2024-02-29 12:00:00','map_name':'Dust2','score1_game':'13','score2_game':'7'}
            documents=[convert({**base,'match_id':str(index)},'digest') for index in range(3000)]
            def batch(start,stop):return {'job_id':str(uuid4()),'batch_id':str(uuid4()),'checkpoint':stop,
                'prepared_at':'2026-01-01T00:00:00+00:00','documents':documents[start:stop]}
            # Every document is sent twice (two jobs) and every third batch is delivered twice.
            batches=[batch(start,start+250) for start in range(0,3000,250) for _ in range(2)]
            deliveries=batches+batches[::3]
            results=await asyncio.gather(*(commands.store(copy.deepcopy(b)) for b in deliveries))
            assert await database.source_documents.count_documents({})==3000
            assert sum(r['inserted'] for r in results[:len(batches)])==3000
            assert sum(r['duplicates'] for r in results[:len(batches)])==3000
            assert (await repo.statistics())['stored_documents']==3000
            assert await database.committed_batches.count_documents({})==len(batches)
            rows=await repo.unsent(1000);assert len(rows)==len(batches)
            await repo.mark_sent(rows);assert await repo.unsent(10)==[]
            assert 'sent_at' in await database.outbox.find_one({'sent':True})
        finally:
            await client.drop_database(database.name)
            await client.close()
    asyncio.run(scenario())
