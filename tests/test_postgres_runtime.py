"""Real PostgreSQL tests in an isolated schema, opt-in with TEST_POSTGRES_URL."""
import asyncio
import json
import os
from uuid import uuid4, UUID
from pathlib import Path
import pytest
import asyncpg
from ingestion_service.infrastructure.database.replay_store import PostgresReplayStore, Conflict

pytestmark=pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'),reason='Requires isolated PostgreSQL test server')

def test_postgres_jobs_outbox_reordering_and_restart():
    async def scenario():
        url=os.environ['TEST_POSTGRES_URL']; schema='test_'+uuid4().hex
        admin=await asyncpg.connect(url)
        await admin.execute(f'CREATE SCHEMA {schema}')
        pool=await asyncpg.create_pool(url,min_size=1,max_size=5,server_settings={'search_path':schema})
        try:
            store=PostgresReplayStore(pool,Path(os.getenv('CORPUS_DIR', 'data/prepared')))
            await asyncio.gather(store.initialize(),PostgresReplayStore(pool,Path(os.getenv('CORPUS_DIR', 'data/prepared'))).initialize())
            key=uuid4().hex
            first,second=await asyncio.gather(store.create_job('kaggle-cs',10,key),store.create_job('kaggle-cs',10,key))
            assert first['id']==second['id']
            with pytest.raises(Conflict):await store.create_job('kaggle-cs',100,key)
            with pytest.raises(ValueError):await store.create_job('../secret',100,uuid4().hex)
            job_id=first['id'];identifier=UUID(job_id)
            await store.change_job(job_id,'pause')
            assert not await store.produce()
            with pytest.raises(Conflict):await store.change_job(job_id,'pause')
            await store.change_job(job_id,'rate',500)
            await store.change_job(job_id,'resume')
            assert await store.produce()
            await pool.execute('UPDATE replay_jobs SET next_at=now() WHERE id=$1',identifier)
            assert await store.produce()
            rows=await pool.fetch('SELECT b.id,b.end_offset,o.payload FROM replay_batches b JOIN replay_outbox o ON o.id=b.id ORDER BY b.start_offset')
            assert len(rows)==2
            assert json.loads(rows[0]['payload'])['documents']
            def completion(row):return {'job_id':job_id,'batch_id':str(row['id']),'checkpoint':row['end_offset'],'inserted':50,'duplicates':0,'rejected':0}
            await store.complete(completion(rows[1]))
            assert (await store.get_job(job_id))['checkpoint']==0
            await store.complete(completion(rows[0]))
            state=await store.get_job(job_id);assert state['checkpoint']==100 and state['inserted']==100
            await store.complete(completion(rows[0]))
            assert (await store.get_job(job_id))['inserted']==100
            restarted=PostgresReplayStore(pool,Path(os.getenv('CORPUS_DIR', 'data/prepared')));await restarted.initialize()
            assert (await restarted.get_job(job_id))['checkpoint']==100
            await pool.execute('UPDATE replay_jobs SET next_at=now() WHERE id=$1',identifier)
            await restarted.produce()
            pending=await pool.fetchrow("SELECT * FROM replay_batches WHERE status='pending'")
            with pytest.raises(ValueError):await restarted.complete({'job_id':job_id,'batch_id':str(pending['id']),'checkpoint':150,'inserted':999,'duplicates':0,'rejected':0})
            assert (await restarted.get_job(job_id))['checkpoint']==100
            await restarted.complete({'job_id':job_id,'batch_id':str(pending['id']),'error':'test failure'})
            assert (await restarted.get_job(job_id))['status']=='failed'
            assert (await restarted.list_jobs(1,20))['total']==1
        finally:
            await pool.close()
            await admin.execute(f'DROP SCHEMA {schema} CASCADE')
            await admin.close()
    asyncio.run(scenario())

