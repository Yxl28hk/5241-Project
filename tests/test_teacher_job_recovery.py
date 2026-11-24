import copy
import io
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.infrastructure.database import get_db
from app.studio import ai_routes, job_store
from app.studio.course_ai import page_refs, CourseAIError, parse_file, validate_result, expand_fields
from test_account_lifecycle import account_app
from test_hosted_runtime import hosted
from test_teacher_features import fixture_document, fixture_result


def test_cancelled_worker_drains_then_expires_and_new_request_runs_once(hosted,monkeypatch):
    app,client,uid=hosted
    monkeypatch.setattr(ai_routes,'ai_settings',lambda:dict(key='test',base='https://example.invalid',model='fake'))
    result=validate_result(fixture_result(),parse_file(fixture_document(),'pptx'))
    model=Mock(side_effect=lambda *a,**kw:copy.deepcopy(result))
    monkeypatch.setattr(ai_routes,'request_course',model)
    owner=f'user:{uid}'
    with app.app_context():
        jid,_,_=job_store.reserve(owner,'first-running-request')
        job_store.update(jid,state='generating')
    config=client.get('/api/studio/ai/config').json
    assert config['active_job_id']==jid
    headers={'X-Studio-CSRF':config['csrf']}
    form=lambda:dict(request_id='second-request',file=(io.BytesIO(fixture_document()),'class.pptx'))
    conflict=client.post('/api/studio/ai/jobs',headers=headers,data=form())
    assert conflict.status_code==409 and conflict.json['job_id']==jid
    model.assert_not_called()
    admin=app.test_client()
    admin.post('/api/auth/login',json={'email':'admin@example.test','password':'admin-password123'})
    assert admin.get('/api/studio/ai/config').json['active_job_id'] is None
    assert admin.get('/api/studio/ai/jobs/'+jid).status_code==404
    cancelled=client.delete('/api/studio/ai/jobs/'+jid,headers=headers)
    assert cancelled.json['in_flight'] is True
    assert client.get('/api/studio/ai/jobs/'+jid).json['state']=='cancelled'
    assert client.post('/api/studio/ai/jobs',headers=headers,data=form()).status_code==409
    with app.app_context():
        db=get_db()
        db.execute("UPDATE studio_ai_jobs SET created_at=NOW()-INTERVAL '6 minutes',updated_at=NOW() WHERE id=%s",(jid,));db.commit()
    assert client.get('/api/studio/ai/config').json['active_job_id'] is None
    final=client.get('/api/studio/ai/jobs/'+jid).json
    assert final['state']=='cancelled' and final['in_flight'] is False
    response=client.post('/api/studio/ai/jobs',headers=headers,data=form())
    assert response.status_code==202,response.json
    assert client.get('/api/studio/ai/jobs/'+response.json['job_id']).json['state']=='done'
    model.assert_called_once()
    with app.app_context():
        job_store.update(jid,state='generating',message='late heartbeat')
        job_store.update(jid,state='done',result={'late':'response'})
        final=job_store.get(owner,jid=jid)
        assert final['state']=='cancelled' and not final['in_flight'] and 'result' not in final


def test_hosted_deadline_does_not_extend_with_progress_updates(hosted):
    app,_,uid=hosted;owner=f'user:{uid}'
    with app.app_context():
        jid,_,_=job_store.reserve(owner,'dead-worker-request')
        db=get_db();db.execute("UPDATE studio_ai_jobs SET created_at=NOW()-INTERVAL '6 minutes',updated_at=NOW() WHERE id=%s",(jid,));db.commit()
        final=job_store.get(owner,jid=jid)
        assert final['state']=='error' and final['error_code']=='task_expired'
        assert job_store.current(owner) is None
        job_store.update(jid,state='done',result={'late':'response'})
        assert job_store.get(owner,jid=jid)['state']=='error'


def test_cancelled_live_worker_releases_slot_when_provider_finishes(hosted,monkeypatch):
    app,client,_=hosted
    monkeypatch.setattr(ai_routes,'ai_settings',lambda:dict(key='test',base='https://example.invalid',model='fake'))
    result=validate_result(fixture_result(),parse_file(fixture_document(),'pptx'))
    started,finish=Event(),Event()
    def provider(*args,**kwargs):
        started.set()
        assert finish.wait(8)
        return copy.deepcopy(result)
    monkeypatch.setattr(ai_routes,'request_course',provider)
    worker=app.test_client()
    worker.post('/api/auth/login',json={'email':'cloud@example.test','password':'test-password'})
    worker_headers={'X-Studio-CSRF':worker.get('/api/studio/ai/config').json['csrf']}
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending=executor.submit(worker.post,'/api/studio/ai/jobs',headers=worker_headers,
            data=dict(request_id='cancel-live-request',file=(io.BytesIO(fixture_document()),'class.pptx')))
        try:
            assert started.wait(5)
            config=client.get('/api/studio/ai/config').json;jid=config['active_job_id']
            response=client.delete('/api/studio/ai/jobs/'+jid,headers={'X-Studio-CSRF':config['csrf']})
            assert response.json['in_flight']
        finally:finish.set()
        assert pending.result(timeout=5).status_code==202
    final=client.get('/api/studio/ai/jobs/'+jid).json
    assert final['state']=='cancelled' and not final['in_flight'] and 'result' not in final
    assert client.get('/api/studio/ai/config').json['active_job_id'] is None


@pytest.mark.parametrize('value,expected',[
    ('1,2',[1,2]),('１，２',[1,2]),('[1,2]',[1,2]),([1,2],[1,2]),
    ('1-3',[1,2,3]),('第1–3页',[1,2,3]),('pages 1, 3',[1,3]),('第1页、第2页',[1,2]),
    ('2; 2; 4',[2,4]),
])
def test_unambiguous_citation_formats(value,expected):
    assert page_refs(value,True)==expected


@pytest.mark.parametrize('value',['0','999','3-1','1-9999999','-1','1.5','somewhere on page 1','[true]',['2'],True,[],{'page':1}])
def test_invalid_citations_still_rejected(value):
    with pytest.raises(CourseAIError):page_refs(value,True)


def test_normalized_references_still_require_actual_source_pages():
    parsed=parse_file(fixture_document(),'pptx')
    data=fixture_result();data['course']['sections'][0]['source_pages']=page_refs('1-2',True)
    with pytest.raises(CourseAIError,match='不存在'):validate_result(data,parsed)
    expanded=expand_fields({'title':'Test','section_1_title':'First','section_1_body':'Text','section_1_pages':[1], 'section_1_quote':'Quote'})
    assert expanded['course']['sections'][0]['source_pages']==[1]
