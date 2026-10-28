"""Verify fresh installs and upgrades from either side of the teacher/quiz merge."""
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from app.infrastructure.migrations import ALL, apply_migrations, initialize_prototype


@pytest.mark.parametrize("previous", ["fresh", "main", "teacher"])
def test_teacher_and_quiz_migrations_preserve_existing_content(previous):
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for isolated PostgreSQL migration checks")
    schema = "merge_test_" + uuid4().hex
    # This test only creates/removes its own random schema, never shared tables.
    with psycopg.connect(url, autocommit=True, row_factory=dict_row) as control:
        control.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            with psycopg.connect(url, row_factory=dict_row) as db:
                db.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                db.commit()
                old = () if previous == "fresh" else tuple(
                    name for name in ALL
                    if (name != "005_course_studio.sql" if previous == "main"
                        else name not in {"005_quiz.sql", "006_quiz_play.sql"})
                )
                apply_migrations(db, old)
                saved_course = None
                if previous != "fresh":
                    saved_course = db.execute(
                        "INSERT INTO courses (title, category, resource_type, author) VALUES (%s, 'test', 'lesson', 'Test teacher') RETURNING id",
                        ("Existing course",),
                    ).fetchone()["id"]
                if previous == "teacher":
                    db.execute(
                        "INSERT INTO course_studio (course_id, content, revision) VALUES (%s, %s, 7)",
                        (saved_course, '{"title": "Keep my draft"}'),
                    )
                assert apply_migrations(db) == [name for name in ALL if name not in old]
                initialize_prototype(db)
                assert apply_migrations(db) == []
                assert {row["version"] for row in db.execute("SELECT version FROM schema_migrations")} == set(ALL)
                assert db.execute("SELECT count(*) AS n FROM quiz_questions").fetchone()["n"] > 0
                assert db.execute("SELECT to_regclass('course_studio') AS name").fetchone()["name"]
                if saved_course:
                    assert db.execute("SELECT title FROM courses WHERE id=%s", (saved_course,)).fetchone()["title"] == "Existing course"
                if previous == "teacher":
                    row = db.execute("SELECT content, revision FROM course_studio WHERE course_id=%s", (saved_course,)).fetchone()
                    assert row["revision"] == 7 and row["content"]["title"] == "Keep my draft"
        finally:
            control.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
