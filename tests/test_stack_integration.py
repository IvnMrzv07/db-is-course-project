"""Opt-in real stack acceptance; never substitutes in-memory storage for databases.
RUN_STACK_TESTS=1 OPERATOR_TOKEN=... python -m pytest -m integration -v
The test adds replay jobs and documents to the local coursework stack.
"""
import os
import json
from pathlib import Path
from datetime import datetime, timezone
import subprocess
import time
from uuid import uuid4
import httpx
import pytest

pytestmark=[pytest.mark.integration,pytest.mark.skipif(os.getenv('RUN_STACK_TESTS')!='1',reason='Requires running Compose stack')]

def test_real_import_search_duplicates_pause_restart_and_persistence():
    base=os.getenv('TEST_BASE_URL','http://127.0.0.1:8080')+'/api/v1'
    with httpx.Client(base_url=base,headers={'Authorization':'Bearer '+os.environ['OPERATOR_TOKEN']},timeout=20) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,**kwargs);response.raise_for_status();return response.json()
        snapshots=call('GET','/snapshots');expected=snapshots[0]['documents']
        start={'snapshot_id':'kaggle-cs','target_rate':10};key=str(uuid4())
        job=call('POST','/replays',json=start,headers={'Idempotency-Key':key})
        assert call('POST','/replays',json=start,headers={'Idempotency-Key':key})['id']==job['id']
        deadline=time.monotonic()+30
        while call('GET',f"/replays/{job['id']}")['inserted']+call('GET',f"/replays/{job['id']}")['duplicates'] < 10:
            assert time.monotonic()<deadline, 'No confirmed batches at rate 10'
            time.sleep(.25)
        call('POST',f"/replays/{job['id']}/pause")
        before=call('GET',f"/replays/{job['id']}")['attempted'];time.sleep(2)
        assert call('GET',f"/replays/{job['id']}")['attempted']==before
        call('PATCH',f"/replays/{job['id']}/rate",json={'target_rate':500})
        call('POST',f"/replays/{job['id']}/resume")
        subprocess.run(['docker','compose','restart','ingestion_worker','content_worker'],check=True,timeout=90)
        def finish(job_id):
            deadline=time.monotonic()+600
            while time.monotonic()<deadline:
                state=call('GET',f'/replays/{job_id}')
                assert state['status']!='failed',state
                if state['status']=='completed':return state
                time.sleep(1)
            pytest.fail('Import deadline exceeded')
        finished=finish(job['id']);assert finished['inserted']+finished['duplicates']==expected
        count=call('GET','/corpus/statistics')['stored_documents'];assert count==expected
        page=call('GET','/documents');assert page['items']
        doc=call('GET','/documents/'+page['items'][0]['id']);assert doc['text']
        assert len(page['items'])==20
        page2=call('GET','/documents',params={'page':2})
        assert not ({d['id'] for d in page['items']} & {d['id'] for d in page2['items']})
        filters={'team':doc['metadata']['team1'],'tournament':doc['metadata']['tournament'],
                 'document_type':doc['metadata']['document_type']}
        filtered=call('GET','/documents',params=filters)
        assert filtered['total']>0
        assert all(d['metadata']['document_type']==filters['document_type'] for d in filtered['items'])
        assert call('GET','/documents',params={'q':'.*'})['total']==0
        assert client.get('/documents',params={'page_size':101}).status_code==422
        assert call('GET','/documents',params={'q':doc['metadata']['team1']})['total']>0
        assert call('GET','/documents',params={'q':'UNLIKELY_'+str(uuid4())})['total']==0
        assert client.get('/documents/'+str(uuid4())).status_code==404
        second=call('POST','/replays',json={**start,'target_rate':500},headers={'Idempotency-Key':str(uuid4())})
        repeated=finish(second['id']);assert repeated['inserted']==0 and repeated['duplicates']==expected
        subprocess.run(['docker','compose','restart','mongo','competition_db'],check=True,timeout=90)
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            try:
                assert call('GET','/corpus/statistics')['stored_documents']==count
                assert call('GET',f"/replays/{second['id']}")['status']=='completed'
                break
            except httpx.HTTPError:time.sleep(1)
        else:pytest.fail('Databases did not recover')
        Path('docs/coursework/stages/stage12-summary/compose-check.json').write_text(json.dumps({
            'verified_at':datetime.now(timezone.utc).isoformat(),
            'expected_documents':expected,'stored_documents':count,
            'first_import':finished,'repeat_import':repeated,
            'checks':['rate_10_to_500','pause_resume','worker_restart_during_import',
                      'idempotent_job_creation','repeat_import_no_duplicates',
                      'search_filters_pagination_404_validation','literal_regex_characters',
                      'database_restart_persistence'],
        },ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
