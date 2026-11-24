"""Cloud regressions using an isolated PostgreSQL schema and a fake AI provider."""
import copy
import io
import json
from unittest.mock import Mock

import pytest
from app import create_app
from app.infrastructure.database import get_db
from app.infrastructure.storage import read_upload, save_upload
from app.studio import ai_routes, job_store
from app.studio.course_ai import parse_file, validate_result
from app.tutor.materials import course_materials
from test_account_lifecycle import account_app
from test_teacher_features import fixture_document, fixture_result
from werkzeug.datastructures import FileStorage


@pytest.fixture
def hosted(account_app):
    settings=dict(account_app.config, HOSTED_RUNTIME=True, UPLOAD_STORAGE='database')
    app=create_app(settings)
    client=app.test_client()
    registered=client.post('/api/auth/register',json={
        'name':'Cloud teacher','email':'cloud@example.test','password':'test-password','role':'teacher'})
    uid=registered.json['user']['id']
    assert registered.status_code==201 and not registered.json['user']['can_upload']
    assert client.post('/api/profile/teacher-application',json={'reason':'Teach software engineering to our class.'}).status_code==200
    admin=app.test_client()
    admin.post('/api/auth/login',json={'email':'admin@example.test','password':'admin-password123'})
    assert admin.post(f'/api/admin/teacher-applications/{uid}/review',json={'decision':'approve','reason':'Reviewed'}).status_code==200
    client.post('/api/auth/login',json={'email':'cloud@example.test','password':'test-password'})
    assert client.get('/api/auth/me').json['user']['can_upload']
    return app,client,uid


def publish(client, blob=None, course_id=None, revision=0):
    content=fixture_result()['course']
    content['revision']=revision
    data={'content':json.dumps(content)}
    if blob is not None:data['file']=(io.BytesIO(blob),'class.pptx')
    return client.open('/api/studio/courses'+(f'/{course_id}' if course_id else ''),
                       method='PATCH' if course_id else 'POST',data=data)


def test_cloud_upload_survives_another_instance_and_tutor_reads_same_file(hosted,tmp_path,monkeypatch):
    app,client,_=hosted
    # No writable upload directory exists in this deployment.
    app.config['UPLOAD_FOLDER']=tmp_path/'absent'/'uploads'
    monkeypatch.setattr('app.infrastructure.storage.upload_folder',Mock(side_effect=AssertionError('must not write locally')))
    blob=fixture_document()
    response=publish(client,blob)
    assert response.status_code==201,response.json
    course=response.json['course'];url=course['file_url']
    second=create_app(dict(app.config,UPLOAD_FOLDER=tmp_path/'another-instance'))
    assert second.test_client().get(url).data==blob
    partial=second.test_client().get(url,headers={'Range':'bytes=0-9'})
    assert partial.status_code==206 and partial.data==blob[:10]
    assert not app.config['UPLOAD_FOLDER'].exists()
    with second.app_context():
        db=get_db()
        row=dict(db.execute('SELECT * FROM courses WHERE id=%s',(course['id'],)).fetchone())
        material=course_materials(second,db,row,None)
        assert any(s['source']=='课件第1页' and 'Pull Request' in s['text'] for s in material['sources'])
    # Same ownership rule applies to replacement and deletion.
    stranger=second.test_client()
    stranger.post('/api/auth/register',json={'name':'Other','email':'other@example.test','password':'test-password'})
    assert publish(stranger,blob,course['id'],1).status_code==403
    assert stranger.delete(f"/api/courses/{course['id']}").status_code==403
    updated=publish(client,b'replacement',course['id'],1)
    assert updated.status_code==200,updated.json
    assert second.test_client().get(url).status_code==404
    new_url=updated.json['course']['file_url']
    assert second.test_client().get(new_url).data==b'replacement'
    assert client.delete(f"/api/courses/{course['id']}").status_code==200
    assert second.test_client().get(new_url).status_code==404


def test_cloud_upload_limits_rollback_and_missing_legacy_file(hosted):
    app,client,_=hosted
    config=client.get('/api/studio/ai/config').json
    assert config['upload_max_mb']==3 and config['max_mb']==3
    assert publish(client,b'x'*(3*1024*1024+1)).status_code==413
    with app.app_context():
        db=get_db()
        assert db.execute('SELECT COUNT(*) AS n FROM uploaded_assets').fetchone()['n']==0
        save_upload(FileStorage(stream=io.BytesIO(b'transaction')),'rollback.pdf')
        db.rollback()
        with pytest.raises(FileNotFoundError):read_upload('rollback.pdf')
        with pytest.raises(ValueError):read_upload('../secret.pdf')
    missing=client.get('/uploads/lost-old-course.pdf')
    assert missing.status_code==404 and '重新上传' in missing.json['error']
    oversized=client.post('/api/studio/courses',data=b'x'*(4*1024*1024+1),content_type='multipart/form-data; boundary=xx')
    assert oversized.status_code==413 and '3MB' in oversized.json['error']


def test_legacy_upload_and_avatar_use_persistent_store(hosted):
    app,client,_=hosted
    response=client.post('/api/courses',data={'title':'Legacy upload','category':'技术','type':'pdf','file':(io.BytesIO(b'course'),'课件.pdf')})
    assert response.status_code==201,response.json
    url=response.json['course']['file_url']
    assert url.endswith('.pdf')
    avatar=client.patch('/api/profile',data={'name':'Teacher','avatar':(io.BytesIO(b'avatar'),'avatar.png')})
    assert avatar.status_code==200,avatar.json
    with app.app_context():
        filenames=[r['filename'] for r in get_db().execute('SELECT filename FROM uploaded_assets').fetchall()]
        assert len(filenames)==2
    assert client.get(url).data==b'course'
    assert client.delete('/api/profile').status_code==200
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) AS n FROM uploaded_assets').fetchone()['n']==0


def test_cloud_ai_is_durable_deduplicated_and_owner_scoped(hosted,monkeypatch):
    app,client,uid=hosted
    monkeypatch.setattr(ai_routes,'ai_settings',lambda:{'key':'test','base':'https://example.invalid','model':'fake'})
    parsed=parse_file(fixture_document(),'pptx')
    result=validate_result(fixture_result(),parsed)
    model=Mock(side_effect=lambda *a,**kw:copy.deepcopy(result))
    monkeypatch.setattr(ai_routes,'request_course',model)
    config=client.get('/api/studio/ai/config').json
    assert config['request_bound']
    headers={'X-Studio-CSRF':config['csrf']}
    form=lambda:{'request_id':'cloud-test-request','file':(io.BytesIO(fixture_document()),'class.pptx')}
    response=client.post('/api/studio/ai/jobs',headers=headers,data=form())
    assert response.status_code==202,response.json
    jid=response.json['job_id']
    # Result is complete before the invocation returns, without a background worker.
    assert client.get('/api/studio/ai/jobs/'+jid).json['state']=='done'
    second=create_app(dict(app.config)).test_client()
    second.post('/api/auth/login',json={'email':'cloud@example.test','password':'test-password'})
    restored=second.get('/api/studio/ai/jobs/request-cloud-test-request')
    assert restored.json['id']==jid and restored.json['state']=='done'
    assert 'result' in restored.json and not {'owner','request_id','key'} & restored.json.keys()
    assert client.post('/api/studio/ai/jobs',headers=headers,data=form()).json['job_id']==jid
    model.assert_called_once()
    admin=app.test_client()
    admin.post('/api/auth/login',json={'email':'admin@example.test','password':'admin-password123'})
    assert admin.get('/api/studio/ai/jobs/'+jid).status_code==404
    assert second.delete('/api/studio/ai/jobs/'+jid).status_code==403
    assert client.delete('/api/studio/ai/jobs/'+jid,headers=headers).status_code==200
    with app.app_context():job_store.update(jid,state='done',result={'late':'response'})
    final=second.get('/api/studio/ai/jobs/'+jid).json
    assert final['state']=='cancelled' and 'result' not in final
    with app.app_context():
        assert get_db().execute('SELECT COUNT(*) AS n FROM courses WHERE owner_id=%s',(uid,)).fetchone()['n']==0


def test_shared_ai_limits_and_stale_worker_release(hosted):
    app,_,uid=hosted
    owner='user:'+str(uid)
    with app.app_context():
        first,fresh,error=job_store.reserve(owner,'request-one')
        assert fresh and not error
        assert job_store.reserve(owner,'request-two')[2][1]==409
        db=get_db();db.execute("UPDATE studio_ai_jobs SET updated_at=NOW()-INTERVAL '9 minutes' WHERE id=%s",(first,));db.commit()
    other=create_app(dict(app.config))
    with other.app_context():
        assert job_store.get(owner,jid=first)['state']=='error'
        second,fresh,error=job_store.reserve(owner,'request-two')
        assert fresh and not error
        job_store.reserve('user:another','request-three')
        assert job_store.reserve('user:third','request-four')[2][1]==429
        job_store.cancel(owner,second)
        assert job_store.reserve(owner,'request-five')[2][1]==409
        assert job_store.reserve(owner,'request-one')[0]==first
