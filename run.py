"""Flask CLI / WSGI entry point. Importing it never initializes the database."""

import os

from app import app, get_db, initialize_database
from app.infrastructure.migrations import initialize_prototype

if __name__ == "__main__":
    with app.app_context():
        initialize_database()
        initialize_prototype(get_db())
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
