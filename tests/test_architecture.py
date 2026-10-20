"""Contract and isolation checks for the modular application layout."""

import ast
import json
import re
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.courses import service as course_service
from app.infrastructure import database

ROOT = Path(__file__).resolve().parents[1]


def test_factory_does_not_connect_and_instances_keep_separate_settings(monkeypatch):
    connect = Mock(side_effect=AssertionError("factory must not connect"))
    monkeypatch.setattr(database.psycopg, "connect", connect)
    first = create_app({"TESTING": True, "DATABASE_URL": "", "SECRET_KEY": "first"})
    second = create_app({"TESTING": True, "SECRET_KEY": "second"})
    assert first.config["SECRET_KEY"] == "first"
    assert second.config["SECRET_KEY"] == "second"
    assert first.test_client().get("/api/auth/me").json == {"user": None}
    connect.assert_not_called()


def test_existing_http_contract_is_preserved():
    application = create_app({"TESTING": True})
    actual = {
        (method, rule.rule)
        for rule in application.url_map.iter_rules()
        for method in rule.methods - {"HEAD", "OPTIONS"}
    }
    expected = {
        tuple(item)
        for item in json.loads((ROOT / "tests/fixtures/http_routes.json").read_text())
    }
    assert actual == expected | {("GET", "/frontend/<path:filename>")}


def test_frontend_assets_load_in_declared_order_and_private_files_stay_private():
    from app.infrastructure.web import SCRIPTS

    client = create_app({"TESTING": True}).test_client()
    html = client.get("/").get_data(as_text=True)
    scripts = re.findall(r'<script src="([^"]+)"', html)
    assert scripts == [f"/frontend/{script}" for script in SCRIPTS]
    for url in scripts + re.findall(r'<link[^>]+href="([^"]+\.css)"', html):
        assert client.get(url).status_code == 200, url
    for url in (
        "/api.js",
        "/app.js",
        "/prototype.js",
        "/study.js",
        "/styles.css",
        "/prototype.css",
    ):
        assert client.get(url).status_code == 200, url
    for url in (
        "/.env",
        "/run.py",
        "/frontend/../config.py",
        "/frontend/index.html",
        "/migrations/001_core.sql",
    ):
        assert client.get(url).status_code == 404, url


def test_course_removal_checks_actor_separately_from_target_learner(monkeypatch):
    connection = Mock()
    permission = Mock(return_value={"id": 7})
    remove = Mock(return_value=Mock(rowcount=1))
    monkeypatch.setattr(course_service, "managed_course", permission)
    monkeypatch.setattr(course_service.repository, "delete_learner", remove)
    result = course_service.remove_course_learner(
        7, 99, actor_id=42, get_db=lambda: connection
    )
    assert "message" in result
    permission.assert_called_once_with(connection, 42, 7)
    remove.assert_called_once_with(connection, (7, 99))
    connection.commit.assert_called_once()


def test_course_search_keeps_query_and_category_independent(monkeypatch):
    connection = Mock()
    search = Mock(return_value=[])
    monkeypatch.setattr(course_service.repository, "search_courses", search)
    result = course_service.courses(
        filters={"q": "Git", "category": "技术"}, get_db=lambda: connection
    )
    assert result == {"courses": []}
    search.assert_called_once_with(connection, "Git", "技术")


def test_business_routes_and_services_do_not_execute_sql():
    for domain in ("auth", "courses", "learning", "tutor", "missions"):
        for filename in ("routes.py", "service.py"):
            path = ROOT / "app" / domain / filename
            tree = ast.parse(path.read_text(encoding="utf-8"))
            assert not any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute"
                for node in ast.walk(tree)
            ), path
