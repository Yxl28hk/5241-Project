"""One PostgreSQL connection per application context; no connection on import."""

from typing import Any

import psycopg
from flask import current_app, g
from psycopg import Connection
from psycopg.rows import dict_row


def get_db() -> Connection[Any]:
    if "db" not in g:
        database_url = current_app.config.get("DATABASE_URL", "")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is not configured. Set it to your Neon PostgreSQL connection string."
            )
        g.db = psycopg.connect(database_url, row_factory=dict_row)
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()
