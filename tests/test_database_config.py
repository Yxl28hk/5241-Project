"""Configuration regression checks that do not need database credentials."""
from unittest.mock import Mock

import pytest
import app as platform


def test_database_url_required_even_with_legacy_demo_flag(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    monkeypatch.setattr(platform, "DATABASE_URL", "")
    connect = Mock()
    monkeypatch.setattr(platform.psycopg, "connect", connect)
    with platform.app.app_context(), pytest.raises(RuntimeError, match="DATABASE_URL"):
        platform.get_db()
    connect.assert_not_called()


def test_postgres_connection_reused_and_closed(monkeypatch):
    connection = Mock()
    connect = Mock(return_value=connection)
    monkeypatch.setattr(platform.psycopg, "connect", connect)
    monkeypatch.setattr(platform, "DATABASE_URL", "postgresql://example.invalid/test")
    with platform.app.app_context():
        assert platform.get_db() is connection
        assert platform.get_db() is connection
        connect.assert_called_once_with(platform.DATABASE_URL, row_factory=platform.dict_row)
    connection.close.assert_called_once()


def test_public_config_contains_no_demo_switch_or_credentials():
    result = platform.app.test_client().get("/api/prototype/config")
    assert result.json == {"database": "postgresql", "tutor_mode": "guided-demo"}
