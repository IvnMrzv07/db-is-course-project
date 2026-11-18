"""Correlated invalid batch -> failed job -> fresh replay, isolated stack only."""
import json,os,subprocess,time
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
import httpx
C=['docker','compose','-p','cs-acceptance','-f','docker-compose.yml','-f','deploy/docker-compose.acceptance.yml']
def dc(*a):
 r=subprocess.run(C+list(a),capture_output=True,text=True,timeout=90);assert r.returncode==0,r.stderr;return r.stdout
base='http://127.0.0.1:8081/api/v1';h={'Authorization':'Bearer '+os.environ['OPERATOR_TOKEN']}
def req(method,path,**kw):
 r=httpx.request(method,base+path,headers=h,timeout=20,**kw);r.raise_for_status();return r.json()
def start(rate):
 r=httpx.post(base+'/replays',headers={**h,'Idempotency-Key':str(uuid4())},json={'target_rate':rate,'snapshot_id':'kaggle-cs'});r.raise_for_status();return r.json()['id']
def wait(i,status):
 end=time.monotonic()+120
 while time.monotonic()<end:
  s=req('GET','/replays/'+i)
  if s['status']==status:return s
  time.sleep(.5)
 raise AssertionError(s)
try:
 dc('stop','content_worker');i=start(10);time.sleep(2)
 dc('exec','-T','ingestion_api','python','-c',"""import asyncio,json
from ingestion_service.infrastructure.messaging.runtime_broker import Broker
async def run():
 b=await Broker().connect();q=await b.channel.get_queue('corpus.store');m=await q.get();payload=json.loads(m.body);payload['documents'][0]['title']='';await b.publish('corpus.store',payload);await m.ack();await b.close()
asyncio.run(run())""")
 dc('start','content_worker');failed=wait(i,'failed');assert failed['error']=='Invalid document',failed
 recovered=wait(start(500),'completed');assert recovered['duplicates']==1000 and recovered['inserted']==0
 data={'verified_at':datetime.now(timezone.utc).isoformat(),'isolated_project':'cs-acceptance','failed_job':failed,'recovery_job':recovered,'stored_documents':req('GET','/corpus/statistics')['stored_documents']}
 Path('docs/coursework/stages/stage12-summary/failed-job-check.json').write_text(json.dumps(data,indent=2)+'\n');print('Correlated failure and fresh replay recovery passed')
finally:dc('start','content_worker')
