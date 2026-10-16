import io
import pytest
import app as platform
from prototype import initialize_prototype


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(platform, "DEMO_MODE", True)
    monkeypatch.setattr(platform, "ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setattr(platform, "UPLOAD_FOLDER", tmp_path)
    monkeypatch.setenv("DEMO_DATABASE_PATH", str(tmp_path / "test.db"))
    platform.app.config.update(TESTING=True, SECRET_KEY="test-only-session-key")
    with platform.app.app_context():
        platform.initialize_database()
        initialize_prototype(platform.get_db())
    return platform.app.test_client()


def register(client, email="student@example.test", role="student"):
    return client.post("/api/auth/register", json={"name":"Test Learner", "email":email, "password":"password123", "role":role})


def test_auth_and_static_exposure(client):
    assert client.get("/api/learning-path").status_code == 401
    assert client.post("/api/tutor", json={}).status_code == 401
    for path in ["/.env", "/app.py", "/demo.db", "/.git/config", "/requirements.txt"]:
        assert client.get(path).status_code == 404
    assert client.get("/prototype.js").status_code == 200
    assert register(client).status_code == 201
    client.post("/api/auth/logout")
    result = client.post("/api/auth/login", json={"email":"student@example.test", "password":"password123"})
    assert result.status_code == 200
    assert "password_hash" not in result.json["user"]
    assert register(client).status_code == 409


def test_progress_persists_and_is_private(client):
    register(client)
    path = client.get("/api/learning-path").json
    assert len(path["modules"]) == 3
    course = path["modules"][0]["id"]
    assert client.patch(f"/api/courses/{course}/progress", json={"progress":100}).status_code == 404
    client.post(f"/api/courses/{course}/learn")
    client.patch(f"/api/courses/{course}/progress", json={"progress":100})
    client.post(f"/api/courses/{course}/learn")
    saved = client.get("/api/learning-path").json
    assert saved["completed"] == 1 and saved["progress"] == 33
    assert saved["next_course_id"] != course
    assert client.get("/api/profile/learning").json["courses"][0]["progress"] == 100
    client.post("/api/auth/logout")
    register(client, "other@example.test")
    assert client.get("/api/learning-path").json["progress"] == 0


@pytest.mark.parametrize("value", [-1, 101, 2.5, True, "50", None])
def test_invalid_progress(client, value):
    register(client)
    assert client.patch("/api/courses/1/progress", json={"progress":value}).status_code == 400


def test_tutor_context_and_validation(client):
    register(client)
    course = client.get("/api/learning-path").json["modules"][0]["id"]
    result = client.post("/api/tutor", json={"course_id":course, "message":"给我提示"})
    assert result.json["mode"] == "guided-demo"
    assert "main" in result.json["answer"]
    for data in [{}, [], {"message":"x"*1001}, {"message":"   "}, {"message":"hi", "course_id":True}]:
        assert client.post("/api/tutor", json=data).status_code == 400
    assert client.post("/api/tutor", json={"course_id":99999, "message":"hi"}).status_code == 404


def test_mission_resume_replay_ownership_and_result(client):
    register(client)
    attempt = client.post("/api/missions/release-rescue/start").json["attempt"]
    attempt_id = attempt["id"]
    assert "points" not in attempt["current"]["choices"][0]
    assert client.post("/api/missions/release-rescue/start").json["attempt"]["id"] == attempt_id
    url = f"/api/missions/attempts/{attempt_id}/answer"
    assert client.post(url, json={"step":0,"choice_id":"fake"}).status_code == 400
    for step, choice in enumerate(["pr", "investigate", "prepare", "rollback"]):
        response = client.post(url, json={"step":step, "choice_id":choice, "score":999})
        assert response.status_code == 200
        assert response.json["attempt"]["score"] == (step+1)*25
        assert client.post(url, json={"step":step,"choice_id":choice}).status_code == 409
    assert response.json["attempt"]["passed"] is True
    assert client.get("/api/learning-path").json["mission"]["best_score"] == 100
    new = client.post("/api/missions/release-rescue/start").json["attempt"]
    assert new["id"] != attempt_id
    client.post("/api/auth/logout")
    register(client, "intruder@example.test")
    assert client.post(url, json={"step":0,"choice_id":"pr"}).status_code == 404


def test_wrong_choices_fail_and_record_feedback(client):
    register(client)
    attempt_id = client.post("/api/missions/release-rescue/start").json["attempt"]["id"]
    for step, choice in enumerate(["main", "skip", "deploy", "wait"]):
        result = client.post(f"/api/missions/attempts/{attempt_id}/answer", json={"step":step,"choice_id":choice})
    assert result.json["attempt"]["score"] == 0
    assert result.json["attempt"]["passed"] is False
    assert len(result.json["attempt"]["history"]) == 4


def test_existing_roles_upload_learners_profile_and_delete(client):
    student = register(client).json["user"]
    assert client.get("/api/profile/courses").status_code == 403
    assert client.get("/api/admin/users").status_code == 403
    assert client.post("/api/courses", data={}).status_code == 403
    client.post("/api/auth/logout")
    register(client, "teacher@example.test", "teacher")
    profile = client.patch("/api/profile", data={"name":"Teacher Renamed"})
    assert profile.json["user"]["can_upload"] is True
    created = client.post("/api/courses", data={"title":"Testing course", "category":"技术", "type":"pdf", "file":(io.BytesIO(b"%PDF-1.4 test"), "test.pdf")})
    assert created.status_code == 201
    course = created.json["course"]["id"]
    file_url = created.json["course"]["file_url"]
    assert client.get(file_url).status_code == 200
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email":student["email"], "password":"password123"})
    client.post(f"/api/courses/{course}/learn")
    client.patch(f"/api/courses/{course}/progress", json={"progress":50})
    client.post("/api/auth/logout")
    register(client, "unrelated@example.test", "teacher")
    assert client.get(f"/api/courses/{course}/learners").status_code == 404
    assert client.delete(f"/api/courses/{course}").status_code == 404
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email":"teacher@example.test", "password":"password123"})
    assert client.get(f"/api/courses/{course}/learners").json["learners"][0]["progress"] == 50
    assert client.delete(f"/api/courses/{course}/learners/{student['id']}").status_code == 200
    assert client.delete(f"/api/courses/{course}").status_code == 200
    assert client.get(file_url).status_code == 404
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email":platform.ADMIN_EMAIL, "password":"test-admin-password"})
    assert client.get("/api/admin/users").status_code == 200
    assert client.get("/api/profile/courses").status_code == 200


def test_seed_idempotent_and_account_cascade(client):
    with platform.app.app_context():
        initialize_prototype(platform.get_db())
        assert platform.get_db().execute("SELECT COUNT(*) AS n FROM prototype_courses").fetchone()["n"] == 3
    register(client)
    client.post("/api/missions/release-rescue/start")
    assert client.delete("/api/profile").status_code == 200
    with platform.app.app_context():
        assert platform.get_db().execute("SELECT COUNT(*) AS n FROM mission_attempts").fetchone()["n"] == 0
