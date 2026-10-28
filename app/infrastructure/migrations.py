"""Apply ordered, additive SQL migrations in the current database/schema."""

from config import BASE_DIR

MIGRATION_DIR = BASE_DIR / "migrations"
CORE = ("001_core.sql",)
LEARNING = ("002_learning.sql", "003_study.sql")
# Keep published filenames stable: history is keyed by the complete filename.
PROTOTYPE = (
    *LEARNING, "004_prototype.sql", "005_quiz.sql", "006_quiz_play.sql",
    "005_course_studio.sql",
)
ALL = (*CORE, *PROTOTYPE)


def apply_migrations(db, names=ALL):
    """Caller owns commit/rollback; concurrent runners serialize per schema.

    Existing installations have no history table: IF NOT EXISTS statements adopt
    their current tables without recreating data. Future changes get a new file.
    """
    db.execute("SELECT pg_advisory_xact_lock(hashtext(current_schema()), 5241)")
    db.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
        version TEXT PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    applied = []
    for name in names:
        if name not in ALL:
            raise ValueError(f"Unknown migration: {name}")
        if db.execute(
            "SELECT version FROM schema_migrations WHERE version = %s", (name,)
        ).fetchone():
            continue
        sql = (MIGRATION_DIR / name).read_text(encoding="utf-8")
        # Migrations contain ordinary DDL only, with no procedural SQL blocks.
        for statement in sql.split(";"):
            if statement.strip():
                db.execute(statement)
        db.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (name,))
        applied.append(name)
    return applied


def initialize_core(db, settings):
    from app.infrastructure.seeds import seed_core

    apply_migrations(db, CORE)
    seed_core(db, settings["ADMIN_EMAIL"], settings["ADMIN_PASSWORD"])


def initialize_prototype(db):
    from app.infrastructure.seeds import seed_lessons, seed_quiz

    apply_migrations(db, PROTOTYPE)
    seed_lessons(db)
    seed_quiz(db)


def initialize_learning(db):
    apply_migrations(db, LEARNING)


def initialize_study(db):
    apply_migrations(db, ("003_study.sql",))
