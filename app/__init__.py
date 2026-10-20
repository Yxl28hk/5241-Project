"""Application factory and compatibility exports for existing integrations."""

from flask import current_app, has_app_context

import config as _config
from app.factory import create_app
from app.infrastructure import database as _database
from app.infrastructure.migrations import initialize_core

psycopg = _database.psycopg
dict_row = _database.dict_row
app = create_app()


def _sync_compatibility_settings():
    """Honor legacy module overrides; new code configures create_app(settings)."""
    target = current_app if has_app_context() else app
    for name in ("DATABASE_URL", "ADMIN_PASSWORD", "UPLOAD_FOLDER"):
        if name in globals():
            target.config[name] = globals()[name]


def get_db():
    _sync_compatibility_settings()
    return _database.get_db()


def initialize_database():
    _sync_compatibility_settings()
    initialize_core(_database.get_db(), current_app.config)


def __getattr__(name):
    if hasattr(_config, name):
        return getattr(_config, name)
    raise AttributeError(name)
