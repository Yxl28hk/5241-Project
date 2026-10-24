"""Compose the modular monolith without querying or seeding the database."""

from flask import Flask

import config
from app.infrastructure.database import close_db, get_db
from app.infrastructure.migrations import (
    ALL,
    apply_migrations,
    initialize_core,
    initialize_learning,
    initialize_prototype,
)


def create_app(settings=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        SECRET_KEY=config.SECRET_KEY,
        DATABASE_URL=config.DATABASE_URL,
        ADMIN_EMAIL=config.ADMIN_EMAIL,
        ADMIN_PASSWORD=config.ADMIN_PASSWORD,
        UPLOAD_FOLDER=config.UPLOAD_FOLDER,
        MAX_CONTENT_LENGTH=config.MAX_FILE_SIZE,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        TUTOR_API_URL=config.TUTOR_API_URL,
        TUTOR_API_KEY=config.TUTOR_API_KEY,
        TUTOR_MODEL=config.TUTOR_MODEL,
    )
    if settings:
        app.config.update(settings)
    app.teardown_appcontext(close_db)

    from app.auth.routes import bp as auth
    from app.courses.routes import bp as courses
    from app.infrastructure.web import bp as web
    from app.learning.routes import bp as learning
    from app.missions.routes import bp as missions
    from app.quiz.routes import bp as quiz
    from app.tutor.routes import bp as tutor

    for blueprint in (web, auth, courses, learning, tutor, missions, quiz):
        app.register_blueprint(blueprint)

    @app.errorhandler(413)
    def file_too_large(_error):
        return {"error": "文件不能超过 500MB"}, 413

    @app.cli.command("migrate")
    def migrate_command():
        """Apply schema migrations only, without creating accounts or content."""
        db = get_db()
        applied = apply_migrations(db, ALL)
        db.commit()
        print(f"Database schema up to date; {len(applied)} migration(s) applied.")

    @app.cli.command("init-db")
    def init_db_command():
        """Create additive schema and seed classroom learning content."""
        initialize_core(get_db(), app.config)
        initialize_prototype(get_db())
        print("Database initialized.")

    @app.cli.command("init-learning")
    def init_learning_command():
        """Upgrade learning tables without reseeding accounts or courses."""
        db = get_db()
        initialize_learning(db)
        db.commit()
        print("Learner schema updated; existing accounts and progress preserved.")

    return app
