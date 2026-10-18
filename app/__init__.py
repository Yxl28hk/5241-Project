"""Application package and compatibility facade.

``run.py`` is the executable entry point. The public Flask objects are
re-exported here so existing ``import app`` integrations keep working.
"""

import run as _entrypoint

app = _entrypoint.app
psycopg = _entrypoint.psycopg
dict_row = _entrypoint.dict_row


def _sync_compatibility_settings() -> None:
    for name in ("DATABASE_URL", "ADMIN_PASSWORD", "UPLOAD_FOLDER"):
        if name in globals():
            setattr(_entrypoint, name, globals()[name])


def get_db():
    _sync_compatibility_settings()
    return _entrypoint.get_db()


def initialize_database():
    _sync_compatibility_settings()
    return _entrypoint.initialize_database()


def __getattr__(name):
    return getattr(_entrypoint, name)
