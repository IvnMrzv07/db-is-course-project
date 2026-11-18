"""Destructive acceptance ONLY on cs-acceptance (isolated volumes, 1000-row fixture)."""
import concurrent.futures, json, os, subprocess, time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import httpx
C=['docker','compose','-p','cs-acceptance','-f','docker-compose.yml','-f','deploy/docker-compose.acceptance.yml']
BASE='http://127.0.0.1:8081/api/v1'
TOKEN=os.environ['OPERATOR_TOKEN'];H={'Authorization':'Bearer '+TOKEN}
evidence={'verified_at':datetime.now(timezone.utc).isoformat(),'fixture_documents':1000,'isolated_project':'cs-acceptance','checks':[]}
def compose(*args,input=None):
 r=subprocess.run(C+list(args),input=input,text=True,encoding='utf-8',capture_output=True,timeout=120)
 if r.returncode:raise RuntimeError(r.stderr[-2000:]+r.stdout[-1000:])
 return r.stdout
def inside(code,service='ingestion_api'):return compose('exec','-T',service,'python','-c',code)
def call(method,path,**kw):
 r=httpx.request(method,BASE+path,headers=H,timeout=20,**kw);r.raise_for_status();return r.json()
def wait(fn,seconds=90):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  try:
   x=fn()
   if x:return x
  except (httpx.HTTPError,KeyError):pass
  time.sleep(.5)
 raise AssertionError('Timed out waiting for recovery')
def start(rate=10,key=None):return httpx.post(BASE+'/replays',headers={**H,'Idempotency-Key':key or str(uuid4())},json={'snapshot_id':'kaggle-cs','target_rate':rate},timeout=20)
def job(i):return call('GET','/replays/'+i)
def completed(i):
 s=job(i);assert s['status']!='failed',s
 return s if s['status']=='completed' else None
try:
 assert call('GET','/snapshots')[0]['documents']==1000
 assert call('GET','/corpus/statistics')['stored_documents']==0
 evidence['checks'].append('fresh_isolated_deployment_empty_database')
 key=str(uuid4())
 with concurrent.futures.ThreadPoolExecutor(4) as ex: responses=list(ex.map(lambda _:start(key=key),range(4)))
 assert all(r.status_code==202 for r in responses)
 ids={r.json()['id'] for r in responses};assert len(ids)==1;i=ids.pop()
 wait(lambda:job(i)['inserted']>=2)
 with concurrent.futures.ThreadPoolExecutor(2) as ex:
  statuses=list(ex.map(lambda _:httpx.post(BASE+f'/replays/{i}/pause',headers=H,timeout=20).status_code,range(2)))
 assert sorted(statuses)==[200,409],statuses
 before=job(i)['attempted'];time.sleep(1);assert job(i)['attempted']==before
 evidence['checks'].append('concurrent_idempotent_creation_and_pause_conflict')
 second=start().json()['id']
 call('POST',f'/replays/{i}/resume')
 compose('kill','-s','SIGKILL','content_worker','ingestion_worker');compose('start','content_worker','ingestion_worker')
 wait(lambda:job(i)['attempted']>before)
 evidence['checks'].append('SIGKILL_both_workers_resume_checkpoint')
 compose('stop','rabbitmq');time.sleep(3)
 call('PATCH',f'/replays/{i}/rate',json={'target_rate':500})
 call('PATCH',f'/replays/{second}/rate',json={'target_rate':500})
 compose('start','rabbitmq')
 a=wait(lambda:completed(i),180);b=wait(lambda:completed(second),180)
 assert a['inserted']+b['inserted']==1000
 assert a['duplicates']+b['duplicates']==1000
 assert a['backlog']==b['backlog']==0
 evidence['concurrent_imports']=[a,b]
 evidence['checks'].append('broker_outage_and_concurrent_imports_no_duplicate_documents')
 # Invalid JSON, non-object JSON, and malformed retry headers must each terminate in DLQ.
 inside("""import asyncio,aio_pika
from ingestion_service.infrastructure.messaging.runtime_broker import Broker
async def run():
 b=await Broker().connect()
 for body in (b'{invalid',b'[]',b'{}'):
  await b.channel.default_exchange.publish(aio_pika.Message(body,headers={'attempt':'not-an-integer'},delivery_mode=2),routing_key='corpus.store')
 await b.close()
asyncio.run(run())""")
 time.sleep(18)
 counts=inside("""import asyncio,json
from ingestion_service.infrastructure.messaging.runtime_broker import Broker
async def run():
 b=await Broker().connect()
 for _ in range(60):
  q=await b.channel.declare_queue('corpus.store.failed',durable=True)
  if q.declaration_result.message_count==3:break
  await asyncio.sleep(1)
 assert q.declaration_result.message_count==3,q.declaration_result.message_count
 attempts=[]
 for _ in range(3):
  m=await q.get();attempts.append(m.headers['attempt']);await m.ack()
 assert attempts==[5,5,5],attempts
 print(json.dumps(attempts));await b.close()
asyncio.run(run())""")
 evidence['checks'].append('three_poison_messages_bounded_to_five_attempts_and_quarantined')
 # Divert a real pending completion into its DLQ; redrive must repair the checkpoint.
 third=start(10).json()['id'];wait(lambda:job(third)['attempted']>=2)
 compose('stop','ingestion_worker');time.sleep(2)
 diverted=inside("""import asyncio,json
from ingestion_service.infrastructure.messaging.runtime_broker import Broker
async def run():
 b=await Broker().connect();q=await b.channel.get_queue('corpus.completed');m=await q.get(fail=False)
 if m is None:
  # Produce one real pending batch and dispatch it while the worker is stopped.
  from ingestion_service.runtime import build_runtime
  pool,store,_=await build_runtime();await store.produce()
  row=await pool.fetchrow('SELECT id,payload FROM replay_outbox WHERE NOT sent ORDER BY created_at LIMIT 1')
  await b.publish('corpus.store',json.loads(row['payload']));await pool.execute('UPDATE replay_outbox SET sent=true WHERE id=$1',row['id']);await pool.close()
  for _ in range(30):
   await asyncio.sleep(.2);m=await q.get(fail=False)
   if m:break
 assert m is not None
 await b.publish('corpus.completed.failed',json.loads(m.body),attempt=5);await m.ack();print(m.body.decode());await b.close()
asyncio.run(run())""")
 compose('start','ingestion_worker')
 compose('exec','-T','ingestion_api','python','-m','ingestion_service.infrastructure.messaging.redrive','corpus.completed','--limit','1')
 call('PATCH',f'/replays/{third}/rate',json={'target_rate':500});wait(lambda:completed(third),180)
 evidence['checks'].append('real_pending_completion_DLQ_redrive_recovers_checkpoint')
 evidence['stored_documents']=call('GET','/corpus/statistics')['stored_documents'];assert evidence['stored_documents']==1000
finally:
 # Always return isolated services to running state; never touch demonstration volumes.
 compose('start','mongo','competition_db','rabbitmq','ingestion_worker','content_worker')
Path('docs/coursework/stages/stage12-summary/resilience-check.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(json.dumps(evidence,indent=2))
