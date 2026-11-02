"""Real isolated PostgreSQL lifecycle checks with local-only mail delivery."""
import json
import os
import re
from uuid import uuid4
import pytest
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from app import create_app
from app.infrastructure.database import get_db
from app.infrastructure.migrations import initialize_core, initialize_prototype


@pytest.fixture
def account_app(tmp_path):
    url=os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to run isolated lifecycle integration')
    schema='account_test_'+uuid4().hex
    with psycopg.connect(url,autocommit=True) as control:
        control.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            app=create_app({'TESTING':True,'SECRET_KEY':'test-only-secret','DATABASE_URL':make_conninfo(url, options=f'-c search_path={schema}'),
                'ADMIN_EMAIL':'admin@example.test','ADMIN_PASSWORD':'admin-password123','MAIL_BACKEND':'file',
                'PUBLIC_BASE_URL':'http://127.0.0.1:5016','MAIL_OUTBOX':tmp_path/'outbox','UPLOAD_FOLDER':tmp_path/'uploads'})
            with app.app_context():
                assert get_db().execute('SELECT current_schema() AS name').fetchone()['name']==schema
                initialize_core(get_db(),app.config);initialize_prototype(get_db())
            yield app
        finally:
            control.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_account_lifecycle_with_local_mail_and_two_devices(account_app):
    app=account_app;a=app.test_client();b=app.test_client();admin=app.test_client()
    email='teacher@example.test';password='initial-password123'
    response=a.post('/api/auth/register',json={'name':'Future Teacher','email':email,'password':password,'role':'teacher'})
    assert response.status_code==201,response.json
    uid=response.json['user']['id']
    assert response.json['user']['role']=='student' and not response.json['user']['can_upload']
    assert '_session_version' not in response.json and 'session_version' not in response.json['user']
    assert a.get('/api/learning-path').status_code==403
    assert a.post('/api/studio/courses').status_code==403
    assert a.post('/api/admin/teacher-applications/1/review',json={'decision':'approve','reason':'self approval'}).status_code==403
    assert admin.post('/api/auth/login',json={'email':'admin@example.test','password':'admin-password123'}).status_code==200
    assert admin.post(f'/api/admin/teacher-applications/{uid}/review',json={'decision':'approve','reason':'review'}).status_code==409
    def mail_token(purpose):
        files=list(app.config['MAIL_OUTBOX'].glob('*.json'))
        messages=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(files,key=lambda p:p.stat().st_mtime_ns)]
        return re.search(r'#account-'+purpose+r'=([A-Za-z0-9_-]+)',messages[-1]['body'])[1]
    assert a.post('/api/auth/verification/request').status_code==200
    first=mail_token('verify')
    assert a.post('/api/auth/verification/request').status_code==200
    token=mail_token('verify')
    assert a.post('/api/auth/verification/confirm',json={'token':first}).status_code==400
    assert a.get('/api/auth/verification/confirm').status_code==405
    assert a.post('/api/auth/password/reset',json={'token':token,'password':'another-pass123'}).status_code==400
    assert a.post('/api/auth/verification/confirm',json={'token':token}).status_code==200
    assert a.post('/api/auth/verification/confirm',json={'token':token}).status_code==400
    assert a.get('/api/auth/me').json['user']['email_verified']
    assert a.get('/api/learning-path').status_code==200
    assert a.post('/api/profile/teacher-application',json={'reason':'Teaching software engineering to our class.'}).status_code==200
    queue=admin.get('/api/admin/teacher-applications').json['applications'];assert queue[0]['id']==uid
    assert admin.post(f'/api/admin/teacher-applications/{uid}/review',json={'decision':'reject','reason':'Please clarify the course.'}).status_code==200
    assert a.get('/api/learning-path').status_code==401
    assert a.post('/api/auth/login',json={'email':email,'password':password}).status_code==200
    assert a.post('/api/profile/teacher-application',json={'reason':'Teaching requirements and testing in a university class.'}).status_code==200
    assert admin.post(f'/api/admin/teacher-applications/{uid}/review',json={'decision':'approve','reason':'Reviewed course details.'}).status_code==200
    assert admin.post(f'/api/admin/teacher-applications/{uid}/review',json={'decision':'approve','reason':'Duplicate'}).status_code==409
    assert a.get('/api/studio/ai/config').status_code==403
    a.post('/api/auth/login',json={'email':email,'password':password})
    assert a.get('/api/auth/me').json['user']['can_upload']
    assert a.get('/api/profile/courses').status_code==200
    b.post('/api/auth/login',json={'email':email,'password':password})
    assert a.patch('/api/profile/password',json={'current_password':password,'new_password':'changed-password123'}).status_code==200
    assert a.get('/api/auth/me').json['user'] is None
    assert b.get('/api/studio/ai/config').status_code==403
    assert b.get('/api/learning-path').status_code==401
    assert b.post('/api/auth/login',json={'email':email,'password':password}).status_code==401
    a.post('/api/auth/login',json={'email':email,'password':'changed-password123'})
    b.post('/api/auth/login',json={'email':email,'password':'changed-password123'})
    known=a.post('/api/auth/password/request',json={'email':email})
    reset=mail_token('reset')
    unknown=a.post('/api/auth/password/request',json={'email':'unknown@example.test'})
    assert known.json==unknown.json and known.status_code==unknown.status_code==200
    from hashlib import sha256
    with app.app_context():
        db=get_db();db.execute("UPDATE account_tokens SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 minute' WHERE token_hash=%s",(sha256(reset.encode()).hexdigest(),));db.commit()
    assert a.post('/api/auth/password/reset',json={'token':reset,'password':'reset-password123'}).status_code==400
    a.post('/api/auth/password/request',json={'email':email});valid=mail_token('reset')
    assert a.post('/api/auth/password/reset',json={'token':valid,'password':'reset-password123'}).status_code==200
    assert a.post('/api/auth/password/reset',json={'token':valid,'password':'different-pass123'}).status_code==400
    assert b.get('/api/auth/me').json['user'] is None
    assert a.post('/api/auth/login',json={'email':email,'password':'reset-password123'}).status_code==200
    with app.app_context():
        rows=get_db().execute('SELECT token_hash FROM account_tokens').fetchall()
        assert all(len(row['token_hash'])==64 and row['token_hash']!=valid for row in rows)
        assert get_db().execute('SELECT count(*) AS n FROM teacher_reviews').fetchone()['n']==2
    app.config['MAIL_BACKEND']='disabled'
    assert a.post('/api/auth/password/request',json={'email':email}).status_code==503


def test_disabled_mail_is_explicit_without_database_access():
    client=create_app({'TESTING':True,'DATABASE_URL':'','MAIL_BACKEND':'disabled'}).test_client()
    response=client.post('/api/auth/password/request',json={'email':'any@example.test'})
    assert response.status_code==503 and 'error' in response.json


def test_local_outbox_cannot_be_enabled_for_public_origin():
    from app.auth.mail import check_delivery, MailUnavailable
    app=create_app({'TESTING':True,'MAIL_BACKEND':'file','PUBLIC_BASE_URL':'https://school.example'})
    with app.app_context(),pytest.raises(MailUnavailable):
        check_delivery()


def test_smtp_uses_tls_and_does_not_log_secret_links(monkeypatch):
    from unittest.mock import MagicMock
    from app.auth import mail
    smtp=MagicMock();smtp.__enter__.return_value=smtp
    factory=MagicMock(return_value=smtp);monkeypatch.setattr(mail.smtplib,'SMTP',factory)
    app=create_app({'TESTING':True,'MAIL_BACKEND':'smtp','PUBLIC_BASE_URL':'https://school.example',
        'MAIL_HOST':'smtp.example','MAIL_PORT':587,'MAIL_SECURITY':'starttls','MAIL_FROM':'noreply@example.test',
        'MAIL_USERNAME':'test-user','MAIL_PASSWORD':'test-only-password'})
    with app.app_context():
        mail.send_account_mail('student@example.test','reset','test-token')
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with('test-user','test-only-password')
    message=smtp.send_message.call_args.args[0]
    assert '#account-reset=test-token' in message.get_content()
    factory.assert_called_once_with('smtp.example',587,timeout=15)
