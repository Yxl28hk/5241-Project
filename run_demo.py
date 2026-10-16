"""Start the explicitly local SQLite demo without a Neon account or API key."""
import os

os.environ["DEMO_MODE"] = "1"

from app import app, get_db, initialize_database
from prototype import initialize_prototype
from werkzeug.security import generate_password_hash


def prepare_demo():
    with app.app_context():
        initialize_database()
        db = get_db()
        initialize_prototype(db)
        for name, email, role in [("演示学生", "student@demo.local", "student"),
                                  ("演示教师", "teacher@demo.local", "teacher")]:
            if db.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone() is None:
                db.execute("INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                           (name, email, generate_password_hash("Demo@123456"), role))
        db.commit()


if __name__ == "__main__":
    prepare_demo()
    print("Local demo: student@demo.local / teacher@demo.local — password: Demo@123456")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=False)
