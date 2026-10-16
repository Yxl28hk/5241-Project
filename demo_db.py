"""Explicit, local-only SQLite adapter for classroom demos; PostgreSQL stays default."""
import sqlite3


class DemoConnection:
    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql, params=()):
        sql = sql.replace("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        sql = sql.replace("%s", "?")
        return self.connection.execute(sql, params)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()
