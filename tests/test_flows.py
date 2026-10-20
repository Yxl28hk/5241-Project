import io
import os
from uuid import uuid4
import pytest
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import app as platform
from prototype import initialize_prototype


@pytest.fixture
def client(tmp_path, monkeypatch):
    database_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to a separate PostgreSQL test database")
    schema = "test_" + uuid4().hex
    connect = psycopg.connect

    class IsolatedConnection(psycopg.Connection):
        def execute(self, query, params=None, **kwargs):
            # Transaction poolers may change sessions after commit/rollback.
            # Reapply the test-only search path inside every transaction.
            super().execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
            return super().execute(query, params, **kwargs)

    def isolated_connect(*args, **kwargs):
        return IsolatedConnection.connect(database_url, row_factory=dict_row, connect_timeout=15)
    monkeypatch.setattr(platform, "DATABASE_URL", database_url)
    monkeypatch.setattr(platform.psycopg, "connect", isolated_connect)
    monkeypatch.setattr(platform, "ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setattr(platform, "UPLOAD_FOLDER", tmp_path)
    platform.app.config.update(TESTING=True, SECRET_KEY="test-only-session-key")
    for key in ("TUTOR_API_URL", "TUTOR_API_KEY", "TUTOR_MODEL"):
        monkeypatch.setitem(platform.app.config, key, "")
    # Each case owns a random schema; cleanup never targets public or application tables.
    with connect(database_url, autocommit=True) as control:
        control.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            with platform.app.app_context():
                platform.initialize_database()
                initialize_prototype(platform.get_db())
                assert platform.get_db().execute("SELECT current_schema() AS name").fetchone()["name"] == schema
            yield platform.app.test_client()
        finally:
            control.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def register(client, email="student@example.test", role="student"):
    return client.post("/api/auth/register", json={"name":"Test Learner", "email":email, "password":"password123", "role":role})


def test_migrations_adopt_existing_schema_and_preserve_user_data(client):
    from app.infrastructure.migrations import ALL, apply_migrations

    user_id = register(client).json["user"]["id"]
    course_id = client.get("/api/learning-path").json["modules"][0]["id"]
    client.post(f"/api/courses/{course_id}/learn")
    client.patch(f"/api/courses/{course_id}/progress", json={"progress": 100})
    with platform.app.app_context():
        db = platform.get_db()
        assert len(db.execute("SELECT version FROM schema_migrations").fetchall()) == len(ALL)
        assert apply_migrations(db) == []
        # Simulate an installation with existing business tables but no migration history.
        db.execute("DELETE FROM schema_migrations")
        assert apply_migrations(db) == list(ALL)
        db.commit()
        assert db.execute("SELECT id FROM users WHERE id=%s", (user_id,)).fetchone()
        assert db.execute(
            "SELECT progress FROM learning_records WHERE user_id=%s AND course_id=%s",
            (user_id, course_id),
        ).fetchone()["progress"] == 100
    result = platform.app.test_cli_runner().invoke(args=["migrate"])
    assert result.exit_code == 0, result.output
    assert "0 migration(s) applied" in result.output


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
    course=client.get("/api/learning-path").json["modules"][0]["id"]
    client.patch(f"/api/courses/{course}/notebook",json={"revision":0,"notes":"升级后保留","task_draft":"草稿"})
    exercise=client.get(f"/api/courses/{course}/exercise").json["exercise"]
    client.post(f"/api/courses/{course}/exercise",json={"version":exercise["version"],"choice_id":"evidence"})
    conversation=client.post(f"/api/courses/{course}/conversation").json["conversation"]
    client.post("/api/tutor",json={"course_id":course,"message":"总结重点","token":conversation["token"],"revision":0,"request_id":str(uuid4())})
    with platform.app.app_context():
        initialize_prototype(platform.get_db())
    assert client.get(f"/api/courses/{course}/notebook").json["notebook"]["notes"] == "升级后保留"
    assert len(client.post(f"/api/courses/{course}/conversation").json["conversation"]["messages"]) == 2
    client.post("/api/missions/release-rescue/start")
    assert client.delete("/api/profile").status_code == 200
    with platform.app.app_context():
        assert platform.get_db().execute("SELECT COUNT(*) AS n FROM mission_attempts").fetchone()["n"] == 0
        for table in ("lesson_notebooks","lesson_exercise_results","lesson_conversations"):
            assert platform.get_db().execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"] == 0


def test_learning_profile_optional_persistent_and_private(client):
    assert client.get("/api/learning-profile").status_code == 401
    register(client)
    assert client.get("/api/learning-profile").json["profile"]["goal"] == ""
    profile = {"goal":"quality", "level":"intermediate", "weekly_hours":5}
    assert client.patch("/api/learning-profile", json=profile).status_code == 200
    assert client.patch("/api/learning-profile", json={"weekly_hours":8}).json["profile"]["goal"] == "quality"
    saved = client.get("/api/learning-path").json
    assert saved["recommendations"][0]["path_id"] == "quality"
    assert "目标匹配" in saved["recommendations"][0]["reason"]
    assert saved["active_path_id"] is None
    client.post("/api/auth/logout")
    register(client, "second-profile@example.test")
    assert client.get("/api/learning-profile").json["profile"]["weekly_hours"] is None
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email":"student@example.test", "password":"password123"})
    assert client.get("/api/learning-profile").json["profile"]["weekly_hours"] == 8
    assert client.patch("/api/learning-profile", json={"goal":"", "level":"", "weekly_hours":None}).status_code == 200


@pytest.mark.parametrize("data", [[], {"goal":[]}, {"goal":"other"}, {"level":None},
    {"weekly_hours":True}, {"weekly_hours":0}, {"weekly_hours":41}, {"weekly_hours":2.5}, {"user_id":99}])
def test_learning_profile_validation(client, data):
    register(client)
    assert client.patch("/api/learning-profile", json=data).status_code == 400


def test_path_selection_resume_switch_and_shared_progress(client):
    register(client)
    catalog = client.get("/api/learning-path").json["catalog"]
    assert len(catalog) == 3
    assert client.post("/api/learning-path/select", json={"path_id":"collaboration"}).status_code == 200
    first = client.get("/api/learning-path").json
    assert len(first["modules"]) == 2
    git, ci = [m["id"] for m in first["modules"]]
    for _ in range(2):
        client.post("/api/learning-path/select", json={"path_id":"collaboration"})
    assert client.get("/api/profile/learning").json["courses"] == []
    client.post(f"/api/courses/{git}/learn")
    client.patch(f"/api/courses/{git}/progress", json={"progress":100})
    client.post(f"/api/courses/{ci}/learn")
    client.patch(f"/api/courses/{ci}/progress", json={"progress":50})
    snapshot = client.get("/api/learning-path").json
    assert snapshot["completion_percent"] == 50  # reading 50% is not completion
    client.post(f"/api/courses/{git}/learn")
    snapshot = client.get("/api/learning-path").json
    assert snapshot["resume_course_id"] == git and snapshot["next_course_id"] == ci
    client.post("/api/learning-path/select", json={"path_id":"quality"})
    quality = client.get("/api/learning-path").json
    assert quality["modules"][0]["progress"] == 50
    client.post(f"/api/courses/{quality['modules'][1]['id']}/learn")
    client.post("/api/learning-path/select", json={"path_id":"collaboration"})
    assert client.get("/api/learning-path").json["resume_course_id"] == git
    client.patch("/api/learning-profile", json={"goal":"engineering"})
    assert client.get("/api/learning-path").json["active_path_id"] == "collaboration"
    client.post("/api/auth/logout")
    register(client, "path-other@example.test")
    assert client.get("/api/learning-path").json["active_path_id"] is None
    assert client.get("/api/learning-path").json["completion_percent"] == 0


@pytest.mark.parametrize("data", [[], {}, {"path_id":True}, {"path_id":[]}, {"path_id":"missing"}])
def test_invalid_path_selection(client, data):
    register(client)
    assert client.post("/api/learning-path/select", json=data).status_code == 400


def test_progress_reset_completion_and_removed_resume(client):
    register(client)
    client.post("/api/learning-path/select", json={"path_id":"collaboration"})
    modules = client.get("/api/learning-path").json["modules"]
    for module in modules:
        client.post(f"/api/courses/{module['id']}/learn")
        client.patch(f"/api/courses/{module['id']}/progress", json={"progress":100})
    snapshot = client.get("/api/learning-path").json
    assert snapshot["completion_percent"] == 100 and snapshot["next_course_id"] is None
    client.patch(f"/api/courses/{modules[0]['id']}/progress", json={"progress":0})
    assert client.get("/api/learning-path").json["next_course_id"] == modules[0]["id"]
    client.delete(f"/api/profile/learning/{modules[1]['id']}")
    snapshot = client.get("/api/learning-path").json
    assert snapshot["resume_course_id"] == modules[0]["id"]
    assert snapshot["completion_percent"] == 0


def test_lesson_content_auth_and_not_implicitly_completed(client):
    assert client.get("/api/courses/1/lesson").status_code == 401
    register(client)
    course = client.get("/api/learning-path").json["modules"][0]["id"]
    result = client.get(f"/api/courses/{course}/lesson")
    assert result.status_code == 200 and "main" in result.json["lesson"]["lesson"]
    assert result.json["lesson"]["progress"] == 0
    assert client.get("/api/profile/learning").json["courses"] == []
    assert client.get("/api/courses/999999/lesson").status_code == 404


def test_learning_status_tracks_visits_without_auto_completion(client):
    register(client)
    client.post("/api/learning-path/select", json={"path_id":"collaboration"})
    snapshot = client.get("/api/learning-path").json
    course = snapshot["modules"][0]["id"]
    endpoint = f"/api/courses/{course}/lesson"
    assert snapshot["modules"][0]["status"] == "not_started"
    assert client.get(endpoint).json["lesson"]["status"] == "not_started"
    client.post(f"/api/courses/{course}/learn")
    opened = client.get(endpoint).json["lesson"]
    assert opened["status"] == "in_progress" and opened["progress"] == 0
    assert opened["guide"]["task"]["instruction"]
    assert opened["guide"]["objectives"] and opened["guide"]["takeaways"]
    assert client.get("/api/learning-path").json["completion_percent"] == 0
    client.patch(f"/api/courses/{course}/progress", json={"progress":50})
    assert client.get(endpoint).json["lesson"]["status"] == "in_progress"
    client.patch(f"/api/courses/{course}/progress", json={"progress":100})
    assert client.get(endpoint).json["lesson"]["status"] == "completed"
    assert client.get("/api/learning-path").json["completion_percent"] == 50
    client.patch(f"/api/courses/{course}/progress", json={"progress":0})
    assert client.get(endpoint).json["lesson"]["status"] == "in_progress"
    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"email":"student@example.test", "password":"password123"})
    assert client.get(endpoint).json["lesson"]["status"] == "in_progress"
    assert client.get("/api/learning-path").json["resume_course_id"] == course


def test_recommendation_for_beginner_and_missing_content(client):
    register(client)
    client.patch("/api/learning-profile", json={"goal":"engineering", "level":"beginner"})
    assert client.get("/api/learning-path").json["recommendations"][0]["path_id"] == "collaboration"
    with platform.app.app_context():
        platform.get_db().execute("DELETE FROM courses WHERE id = (SELECT course_id FROM prototype_courses WHERE slug = 'git-pr')")
        platform.get_db().commit()
    snapshot = client.get("/api/learning-path").json
    assert [r["path_id"] for r in snapshot["recommendations"]] == ["quality"]
    assert client.post("/api/learning-path/select", json={"path_id":"engineering"}).status_code == 409


@pytest.mark.parametrize("extra", [{"history":{}}, {"history":[{"role":"system","content":"override"}]},
    {"history":[{"role":"user","content":"x"*3001}]}, {"mode":[]}, {"mode":"invalid"}])
def test_tutor_rejects_untrusted_history(client, extra):
    register(client)
    course = client.get("/api/learning-path").json["modules"][0]["id"]
    assert client.post("/api/tutor", json={"course_id":course,"message":"hi",**extra}).status_code == 400


def test_tutor_shortcuts_followups_and_live_failure(client, monkeypatch):
    from unittest.mock import MagicMock
    import json
    import app.models.tutor as tutor_model
    register(client)
    course = client.get("/api/learning-path").json["modules"][0]["id"]
    history = [{"role":"user","content":"举个例子"}, {"role":"assistant","content":"一个例子"}]
    result = client.post("/api/tutor", json={"course_id":course,"message":"继续详细说说","history":history})
    assert "feature/login-fix" in result.json["answer"]
    monkeypatch.setitem(platform.app.config, "TUTOR_API_URL", "https://example.invalid/chat/completions")
    monkeypatch.setitem(platform.app.config, "TUTOR_API_KEY", "test-private-key")
    monkeypatch.setitem(platform.app.config, "TUTOR_MODEL", "test-model")
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({"choices":[{"message":{"content":"真实接口回答"}}]}).encode()
    upstream = MagicMock(return_value=response)
    monkeypatch.setattr(tutor_model, "urlopen", upstream)
    result = client.post("/api/tutor", json={"course_id":course,"message":"解释一下","history":history})
    assert result.json["mode"] == "live" and result.json["answer"] == "真实接口回答"
    payload = json.loads(upstream.call_args.args[0].data)
    assert "main" in payload["messages"][0]["content"]
    assert payload["messages"][1:3] == history
    assert "test-private-key" not in client.get("/api/prototype/config").text
    upstream.side_effect = TimeoutError("secret upstream error")
    result = client.post("/api/tutor", json={"course_id":course,"message":"hi"})
    assert result.status_code == 502 and "secret" not in result.text
    result = client.post("/api/tutor", json={"course_id":course,"message":"总结重点","mode":"guided-demo"})
    assert result.status_code == 200 and result.json["mode"] == "guided-demo"


def test_fixed_exercises_grade_on_server_restore_and_do_not_complete(client):
    assert client.get("/api/courses/1/exercise").status_code == 401
    register(client)
    modules=client.get("/api/learning-path").json["modules"]
    correct_choices={"git-pr":"evidence","ci-testing":"reproduce","safe-release":"recover"}
    for module in modules:
        url=f"/api/courses/{module['id']}/exercise"
        initial=client.get(url).json
        assert initial["result"] is None and "correct" not in initial["exercise"]
        exercise=initial["exercise"]
        correct=correct_choices[module["slug"]]
        wrong=next(c["id"] for c in exercise["choices"] if c["id"] != correct)
        result=client.post(url,json={"version":exercise["version"],"choice_id":wrong,"correct":True,"score":100})
        assert result.json["result"]["correct"] is False
        assert result.json["result"]["explanation"]
        assert client.post(url,json={"version":exercise["version"],"choice_id":correct}).json["result"]["correct"] is True
        assert client.get(url).json["result"]["attempts"] == 2
    assert client.get("/api/learning-path").json["completion_percent"] == 0
    client.post("/api/auth/logout")
    register(client,"other-practice@example.test")
    assert client.get(f"/api/courses/{modules[0]['id']}/exercise").json["result"] is None


def test_account_notebook_persistence_conflict_and_privacy(client):
    register(client)
    course=client.get("/api/learning-path").json["modules"][0]["id"]
    url=f"/api/courses/{course}/notebook"
    assert client.get(url).json["notebook"]["revision"] == 0
    first=client.patch(url,json={"revision":0,"notes":"我的笔记 <script> 不执行","task_draft":"交接说明"})
    assert first.status_code == 200 and first.json["notebook"]["revision"] == 1
    assert client.patch(url,json={"revision":0,"notes":"旧窗口覆盖"}).status_code == 409
    second=client.patch(url,json={"revision":1,"notes":"窗口二更新"})
    assert second.json["notebook"]["task_draft"] == "交接说明"
    assert client.patch(url,json={"revision":1,"task_draft":"旧草稿"}).status_code == 409
    client.post("/api/auth/logout")
    register(client,"other-notebook@example.test")
    assert client.get(url).json["notebook"]["notes"] == ""
    client.post("/api/auth/logout")
    client.post("/api/auth/login",json={"email":"student@example.test","password":"password123"})
    assert client.get(url).json["notebook"]["notes"] == "窗口二更新"
    assert client.patch(url,json={"revision":2,"notes":"","task_draft":""}).json["notebook"]["revision"] == 3


def test_study_input_validation_and_missing_content(client):
    register(client)
    course=client.get("/api/learning-path").json["modules"][0]["id"]
    for data in [[],{}, {"revision":True,"notes":"x"}, {"revision":0,"notes":[]},
                 {"revision":0,"notes":"x"*12001}, {"revision":0,"task_draft":"x"*4001},
                 {"revision":0,"notes":"x","user_id":99}]:
        assert client.patch(f"/api/courses/{course}/notebook",json=data).status_code == 400
    for data in [{},{"choice_id":[]},{"version":"old","choice_id":"evidence"}]:
        assert client.post(f"/api/courses/{course}/exercise",json=data).status_code == 400
    for extra in [{"context_key":"section-99"},{"context_key":[]},{"action":"hint","context_key":"task","hint_step":True},
                  {"action":"reference","context_key":"overview"},{"history":[{"role":[],"content":"x"}]}]:
        assert client.post("/api/tutor",json={"course_id":course,"message":"问题",**extra}).status_code == 400
    for suffix in ["exercise","notebook"]:
        assert client.get(f"/api/courses/999999/{suffix}").status_code == 404
    assert client.post("/api/courses/999999/conversation").status_code == 404


def test_recent_conversation_hints_retry_reset_and_private_restore(client):
    register(client)
    course=client.get("/api/learning-path").json["modules"][0]["id"]
    url=f"/api/courses/{course}/conversation"
    conversation=client.post(url).json["conversation"]
    payload={"course_id":course,"message":"解释这一段","context_key":"section-0","token":conversation["token"],
             "revision":0,"request_id":str(uuid4())}
    first=client.post("/api/tutor",json=payload)
    assert first.status_code == 200 and first.json["context"]["focus_title"] == "先隔离修改，再提交证据"
    assert len(first.json["conversation"]["messages"]) == 2
    assert client.post("/api/tutor",json=payload).json["conversation"]["revision"] == 1
    assert client.post("/api/tutor",json={**payload,"message":"不同问题"}).status_code == 409
    assert client.post("/api/tutor",json={**payload,"request_id":str(uuid4())}).status_code == 409
    for step in [1,2]:
        conversation=client.post(url).json["conversation"]
        reply=client.post("/api/tutor",json={**payload,"revision":conversation["revision"],"request_id":str(uuid4()),
            "message":f"第{step}步提示","action":"hint","hint_step":step,"context_key":"task"})
        assert reply.json["label"] == "预设分步提示"
        assert f"第 {step} 步" in reply.json["answer"]
        assert reply.json["conversation"]["messages"][-1]["hint_step"] == step
    conversation=client.post(url).json["conversation"]
    old_token=conversation["token"]
    client.post("/api/auth/logout")
    register(client,"other-conversation@example.test")
    assert client.post(url).json["conversation"]["messages"] == []
    assert client.post("/api/tutor",json=payload).status_code == 409
    client.post("/api/auth/logout")
    client.post("/api/auth/login",json={"email":"student@example.test","password":"password123"})
    restored=client.post(url).json["conversation"]
    assert len(restored["messages"]) == 6
    reset=client.delete(url,json={"token":restored["token"],"revision":restored["revision"]})
    assert reset.status_code == 200 and reset.json["conversation"]["messages"] == []
    assert reset.json["conversation"]["token"] != old_token
    assert client.post("/api/tutor",json=payload).status_code == 409


def test_reset_blocks_late_model_response_and_focus_is_grounded(client,monkeypatch):
    from unittest.mock import MagicMock
    import json
    import app.models.tutor as tutor_model
    register(client)
    course=client.get("/api/learning-path").json["modules"][0]["id"]
    current=client.post(f"/api/courses/{course}/conversation").json["conversation"]
    for key,value in [("TUTOR_API_URL","https://example.invalid/chat/completions"),("TUTOR_API_KEY","private-test"),("TUTOR_MODEL","test")]:
        monkeypatch.setitem(platform.app.config,key,value)
    response=MagicMock()
    response.__enter__.return_value.read.return_value=b'{"choices":[{"message":{"content":"late answer"}}]}'
    def upstream(req,**kwargs):
        instructions=json.loads(req.data)["messages"][0]["content"]
        assert "focused_content" in instructions and "先隔离修改" in instructions
        db=platform.get_db()
        db.execute("UPDATE lesson_conversations SET token=%s,revision=0,messages='[]' WHERE course_id=%s",(uuid4().hex,course))
        db.commit()
        return response
    monkeypatch.setattr(tutor_model,"urlopen",upstream)
    result=client.post("/api/tutor",json={"course_id":course,"message":"解释","context_key":"section-0",
        "token":current["token"],"revision":0,"request_id":str(uuid4())})
    assert result.status_code == 409
    assert client.post(f"/api/courses/{course}/conversation").json["conversation"]["messages"] == []
