"""Real PostgreSQL tests in an isolated schema, opt-in with TEST_POSTGRES_URL."""
import asyncio
import json
import os
from uuid import uuid4, UUID
from pathlib import Path
import pytest
import asyncpg
from ingestion_service.infrastructure.database.replay_store import PostgresReplayStore, ProductionLimits, Conflict

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
            reference=json.loads(rows[0]['payload'])
            assert 'documents' not in reference and (reference['start'],reference['end'])==(0,50)
            message=store.materialize(reference)
            assert len(message['documents'])==50 and message['checkpoint']==50 and message['batch_id']==str(rows[0]['id'])
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



def test_unlimited_rate_reference_dispatch_and_checkpoint_index():
    async def scenario():
        url=os.environ['TEST_POSTGRES_URL']; schema='test_'+uuid4().hex
        admin=await asyncpg.connect(url)
        await admin.execute(f'CREATE SCHEMA {schema}')
        pool=await asyncpg.create_pool(url,min_size=1,max_size=5,server_settings={'search_path':schema})
        try:
            store=PostgresReplayStore(pool,Path(os.getenv('CORPUS_DIR','data/prepared')),limits=ProductionLimits(500,1500))
            await store.initialize();await store.initialize()  # migration 003 is repeatable
            job=await store.create_job('kaggle-cs',0,uuid4().hex);identifier=UUID(job['id'])
            with pytest.raises(asyncpg.CheckViolationError):
                await pool.execute('UPDATE replay_jobs SET target_rate=5 WHERE id=$1',identifier)
            # MAX: no pacing between batches, only the outstanding window stops the producer.
            assert [await store.produce() for _ in range(4)]==[True,True,True,False]
            stored=await pool.fetchval('SELECT max(pg_column_size(payload)) FROM replay_outbox');assert stored<1000
            published=[]
            async def publish(queue,message):
                if len(published)==2:raise ConnectionError('broker down')
                published.append((queue,message))
            with pytest.raises(ConnectionError):await store.dispatch(publish)
            assert await pool.fetchval('SELECT count(*) FROM replay_outbox WHERE NOT sent')==3  # nothing lost on failure
            published.clear()
            async def confirm(queue,message):published.append((queue,message))
            assert await store.dispatch(confirm)==3 and await store.dispatch(confirm)==0
            assert [(q,m['checkpoint'],len(m['documents'])) for q,m in published]==[('corpus.store',n,500) for n in (500,1000,1500)]
            for _,message in published:
                await store.complete({'job_id':job['id'],'batch_id':message['batch_id'],'checkpoint':message['checkpoint'],
                    'inserted':500,'duplicates':0,'rejected':0})
            assert (await store.get_job(job['id']))['checkpoint']==1500 and await store.produce()
            # The checkpoint query must not walk finished batches.
            await pool.execute("INSERT INTO replay_batches(id,job_id,start_offset,end_offset,status) SELECT gen_random_uuid(),$1,-n,1-n,'completed' FROM generate_series(1,60000) n",identifier)
            await pool.execute('ANALYZE replay_batches')
            plan=json.loads(await pool.fetchval("EXPLAIN (ANALYZE,FORMAT JSON) SELECT min(start_offset) FROM replay_batches WHERE job_id='"+job['id']+"' AND created_at>='2000-01-01' AND status!='completed'"))
            def removed(node):return node.get('Rows Removed by Filter',0)+sum(removed(child) for child in node.get('Plans',()))
            assert removed(plan[0]['Plan'])<10
            # A reference to input that changed after staging fails the job instead of blocking the queue.
            manifest,records=store.catalog['kaggle-cs'];store.catalog['kaggle-cs']=({**manifest,'jsonl_sha256':'changed'},records)
            assert await store.dispatch(confirm)==1
            state=await store.get_job(job['id']);assert (state['status'],state['error'])==('failed','Snapshot changed')
            assert len(published)==3
            # Cancelling drops what was not published yet; a batch already on its way still completes.
            store.catalog['kaggle-cs']=(manifest,records)
            job=await store.create_job('kaggle-cs',0,uuid4().hex);assert await store.produce();assert await store.produce()
            published.clear();assert await store.dispatch(confirm,limit=1)==1
            with pytest.raises(Conflict,match='active'):await store.purge_jobs()
            state=await store.cancel_job(job['id']);assert state['status']=='cancelled' and await store.dispatch(confirm)==0
            message=published[0][1]
            await store.complete({'job_id':job['id'],'batch_id':message['batch_id'],'checkpoint':500,'inserted':500,'duplicates':0,'rejected':0})
            state=await store.get_job(job['id']);assert (state['status'],state['inserted'],state['checkpoint'])==('cancelled',500,500)
            assert not await store.produce()
            with pytest.raises(Conflict):await store.cancel_job(job['id'])
            with pytest.raises(LookupError):await store.cancel_job(uuid4())
            assert await store.purge_jobs()==2 and (await store.list_jobs(1,20))['total']==0
        finally:
            await pool.close()
            await admin.execute(f'DROP SCHEMA {schema} CASCADE')
            await admin.close()
    asyncio.run(scenario())


LEGACY_DDL = """
CREATE TABLE replay_jobs (id uuid PRIMARY KEY, idempotency_key text UNIQUE NOT NULL, request_hash text NOT NULL,
 snapshot_id text NOT NULL, snapshot_hash text NOT NULL, total integer NOT NULL, status text NOT NULL,
 target_rate integer NOT NULL, produced integer NOT NULL DEFAULT 0, checkpoint integer NOT NULL DEFAULT 0,
 inserted integer NOT NULL DEFAULT 0, duplicates integer NOT NULL DEFAULT 0, rejected integer NOT NULL DEFAULT 0,
 validation_rejected integer NOT NULL DEFAULT 0, error text, next_at timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE replay_batches (id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES replay_jobs(id),
 start_offset integer NOT NULL, end_offset integer NOT NULL, status text NOT NULL DEFAULT 'pending', UNIQUE(job_id, start_offset));
CREATE TABLE replay_outbox (id uuid PRIMARY KEY REFERENCES replay_batches(id), payload jsonb NOT NULL,
 sent boolean NOT NULL DEFAULT false, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX replay_outbox_pending ON replay_outbox(created_at) WHERE NOT sent;
CREATE INDEX replay_batches_pending ON replay_batches(job_id,start_offset) WHERE status = 'pending';
"""


def test_partition_migration_default_rescue_and_retention(tmp_path):
    """Legacy heap tables with 10..0-day-old rows -> partitioned tables -> retention with guards."""
    from datetime import datetime, timedelta, timezone
    from ingestion_service.infrastructure.database import partitioning
    from ingestion_service.infrastructure.database.partitioning import PartitionPolicy, partition_name, utc_day

    async def scenario():
        url=os.environ['TEST_POSTGRES_URL']; schema='test_'+uuid4().hex
        admin=await asyncpg.connect(url)
        await admin.execute(f'CREATE SCHEMA {schema}')
        pool=await asyncpg.create_pool(url,min_size=1,max_size=5,server_settings={'search_path':schema})
        try:
            now=datetime.now(timezone.utc); today=utc_day(now)
            await pool.execute(LEGACY_DDL)
            job=uuid4()
            await pool.execute("INSERT INTO replay_jobs(id,idempotency_key,request_hash,snapshot_id,snapshot_hash,total,status,target_rate,created_at)"
                               " VALUES($1,'k','h','kaggle-cs','x',100,'running',100,$2)",job,now-timedelta(days=12))
            # age (days) -> (batch status, outbox sent)
            plan={10:('completed',True),9:('completed',False),8:('pending',True),0:('completed',True)}
            for index,(age,(status,sent)) in enumerate(plan.items()):
                batch=uuid4()
                await pool.execute('INSERT INTO replay_batches VALUES($1,$2,$3,$4,$5)',batch,job,index*10,index*10+10,status)
                await pool.execute('INSERT INTO replay_outbox VALUES($1,$2,$3,$4)',batch,'{"documents":[]}',sent,now-timedelta(days=age))
            # 1) migration of existing rows (twice: second start must be a no-op)
            store=PostgresReplayStore(pool,tmp_path,PartitionPolicy(ahead_days=1,retention_days=7))
            await asyncio.gather(store.initialize(),PostgresReplayStore(pool,tmp_path).initialize())
            kinds=dict(await pool.fetch("SELECT relname,relkind::text FROM pg_class WHERE relnamespace=$1::regnamespace AND relname IN ('replay_batches','replay_outbox')",schema))
            assert kinds=={'replay_batches':'p','replay_outbox':'p'}
            assert await pool.fetchval("SELECT count(*) FROM pg_class WHERE relnamespace=$1::regnamespace AND relname LIKE '%legacy%'",schema)==0
            assert await pool.fetchval('SELECT count(*) FROM replay_batches')==4==await pool.fetchval('SELECT count(*) FROM replay_outbox')
            assert await pool.fetchval('SELECT count(*) FROM replay_batches b JOIN replay_outbox o ON o.id=b.id AND o.created_at=b.created_at')==4
            names={row['name'] for row in await partitioning.list_partitions(pool)}
            for age in (10,9,8,0,-1):
                day=today-timedelta(days=age)
                assert {partition_name('replay_batches',day),partition_name('replay_outbox',day)}<=names
            assert {'replay_batches_default','replay_outbox_default'}<=names
            # 2) a write for a day without partition lands in DEFAULT and is moved out by maintenance
            future=now+timedelta(days=5); batch=uuid4()
            await pool.execute('INSERT INTO replay_batches(id,job_id,start_offset,end_offset,status,created_at) VALUES($1,$2,1000,1010,$3,$4)',batch,job,'completed',future)
            await pool.execute('INSERT INTO replay_outbox(id,payload,sent,created_at) VALUES($1,$2,true,$3)',batch,'{}',future)
            assert await pool.fetchval('SELECT count(*) FROM replay_outbox_default')==1
            created=await store.ensure_partitions()
            assert created==[utc_day(future).isoformat()]
            assert await pool.fetchval('SELECT count(*) FROM replay_outbox_default')==0==await pool.fetchval('SELECT count(*) FROM replay_batches_default')
            assert await pool.fetchval(f"SELECT count(*) FROM {partition_name('replay_outbox',utc_day(future))}")==1
            # 3) retention: 10d dropped; 9d has an unsent row; 8d has a pending batch; today kept
            result=await store.maintain_partitions()
            actions={entry['day']:entry['action'] for entry in result['retention']}
            day=lambda age:(today-timedelta(days=age)).isoformat()
            assert actions=={day(10):'dropped',day(9):'skipped',day(8):'skipped'}
            names={row['name'] for row in await partitioning.list_partitions(pool)}
            assert partition_name('replay_outbox',today-timedelta(days=10)) not in names
            assert partition_name('replay_batches',today-timedelta(days=10)) not in names
            assert partition_name('replay_outbox',today) in names
            assert await pool.fetchval('SELECT count(*) FROM replay_outbox')==4
            # 4) once the outbox row is sent and the batch completed, the next cycle drops them
            await pool.execute('UPDATE replay_outbox SET sent=true'); await pool.execute("UPDATE replay_batches SET status='completed'")
            assert [e['action'] for e in (await store.maintain_partitions(dry_run=True))['retention']]==['would_drop','would_drop']
            actions=[e['action'] for e in (await store.maintain_partitions())['retention']]
            assert actions==['dropped','dropped']
            assert await pool.fetchval('SELECT count(*) FROM replay_outbox')==2
            # 5) the partitioned tables still accept the normal produce/complete path after cleanup
            assert (await store.maintain_partitions())['retention']==[]
        finally:
            await pool.close()
            await admin.execute(f'DROP SCHEMA {schema} CASCADE')
            await admin.close()
    asyncio.run(scenario())
