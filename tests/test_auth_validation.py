from unittest.mock import Mock
import pytest
from app import create_app
from app.auth import service, routes, security


@pytest.mark.parametrize("value", [None, [], [1], "text", 7, True])
@pytest.mark.parametrize("action", ["register", "login", "update_password"])
def test_invalid_auth_objects_never_touch_database(value, action):
    db = Mock(side_effect=AssertionError("invalid input queried database"))
    kwargs = {"data": value, "get_db": db}
    if action == "update_password":
        kwargs["user_id"] = 1
    assert getattr(service, action)(**kwargs)[1] == 400
    db.assert_not_called()


@pytest.mark.parametrize("override", [
    {"email": "not-an-email"}, {"email": None}, {"name": "x" * 41},
    {"password": " " * 8}, {"password": "x" * 129}, {"password": None}, {"role": "admin"},
])
def test_registration_rejects_invalid_fields(override):
    result = service.register(data={"name": "Teacher", "email": "teacher@example.test", "password": "password123", **override}, get_db=Mock())
    assert result[1] == 400


def test_login_rotates_session_and_me_clears_deleted_account(monkeypatch):
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    client = app.test_client()
    monkeypatch.setattr(service, "login", lambda **kw: {"user": {"id": 2}})
    with client.session_transaction() as session:
        session.update(user_id=1, studio_ai_csrf="old-account-token")
    assert client.post('/api/auth/login', json={}).status_code == 200
    with client.session_transaction() as session:
        assert dict(session) == {"user_id": 2, "session_version": 0}
    monkeypatch.setattr(service, "me", lambda **kw: {"user": None})
    assert client.get('/api/auth/me').json == {"user": None}
    with client.session_transaction() as session:
        assert not session


def test_deleted_account_cannot_use_protected_routes(monkeypatch):
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    client = app.test_client()
    monkeypatch.setattr(security, "get_db", Mock())
    monkeypatch.setattr(security, "find_role", lambda *a: None)
    with client.session_transaction() as session:
        session['user_id'] = 999
    assert client.get('/api/learning-path').status_code == 401
    with client.session_transaction() as session:
        assert not session


@pytest.mark.parametrize("headers", [{"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site"}])
def test_cross_site_login_and_writes_are_blocked(headers):
    client = create_app({"TESTING": True}).test_client()
    for path in ['/api/auth/login', '/api/auth/register', '/api/auth/logout', '/api/studio/courses']:
        assert client.post(path, json={}, headers=headers).status_code == 403


def test_login_throttling_expires_and_does_not_lock_other_accounts(monkeypatch):
    from app.auth import throttle
    now = [1000.0]
    monkeypatch.setattr(throttle, "monotonic", lambda: now[0])
    monkeypatch.setattr(service, "login", lambda **kw: ({"error": "invalid"}, 401))
    client = create_app({"TESTING": True}).test_client()
    for _ in range(20):
        assert client.post('/api/auth/login', json={"email": "a@example.test"}).status_code == 401
    response = client.post('/api/auth/login', json={"email": "a@example.test"})
    assert response.status_code == 429 and int(response.headers['Retry-After']) > 0
    assert client.post('/api/auth/login', json={"email": "b@example.test"}).status_code == 401
    now[0] += 301
    assert client.post('/api/auth/login', json={"email": "a@example.test"}).status_code == 401
