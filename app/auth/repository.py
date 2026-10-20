"""Auth SQL operations; callers own commit/rollback."""


def find_public_user(db, params):
    return db.execute(
        "SELECT id, name, email, avatar_filename, role FROM users WHERE id = %s", params
    ).fetchone()


def list_accounts(db):
    return db.execute(
        """SELECT id, name, email, role, avatar_filename, created_at
        FROM users ORDER BY created_at DESC, id DESC"""
    ).fetchall()


def list_owned_courses(db):
    return db.execute(
        """SELECT id, owner_id, title, category, resource_type, description,
        author, duration, cover, badge, filename, created_at
        FROM courses WHERE owner_id IS NOT NULL
        ORDER BY created_at DESC, id DESC"""
    ).fetchall()


def list_learning_records(db):
    return db.execute(
        """SELECT l.user_id, l.course_id, l.progress, l.started_at, l.updated_at,
        c.title, c.category, c.resource_type, c.author
        FROM learning_records l
        JOIN courses c ON c.id = l.course_id
        ORDER BY l.updated_at DESC"""
    ).fetchall()


def insert_user(db, params):
    return db.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        params,
    )


def find_registered_user(db, params):
    return db.execute(
        "SELECT id, name, email, role, avatar_filename FROM users WHERE id = %s", params
    ).fetchone()


def find_user_by_email(db, params):
    return db.execute("SELECT * FROM users WHERE email = %s", params).fetchone()


def find_avatar(db, params):
    return db.execute(
        "SELECT avatar_filename FROM users WHERE id = %s", params
    ).fetchone()


def list_account_files(db, params):
    return db.execute(
        "SELECT filename FROM courses WHERE owner_id = %s", params
    ).fetchall()


def delete_account_learning(db, params):
    return db.execute("DELETE FROM learning_records WHERE user_id = %s", params)


def delete_owned_courses(db, params):
    return db.execute("DELETE FROM courses WHERE owner_id = %s", params)


def delete_user(db, params):
    return db.execute("DELETE FROM users WHERE id = %s", params)


def update_name_and_avatar(db, params):
    return db.execute(
        "UPDATE users SET name = %s, avatar_filename = %s WHERE id = %s", params
    )


def update_name(db, params):
    return db.execute("UPDATE users SET name = %s WHERE id = %s", params)


def find_updated_user(db, params):
    return db.execute(
        "SELECT id, name, email, role, avatar_filename FROM users WHERE id = %s", params
    ).fetchone()


def find_password_hash(db, params):
    return db.execute(
        "SELECT password_hash FROM users WHERE id = %s", params
    ).fetchone()


def update_password_hash(db, params):
    return db.execute("UPDATE users SET password_hash = %s WHERE id = %s", params)


def find_role(db, user_id):
    return db.execute("SELECT role FROM users WHERE id = %s", (user_id,)).fetchone()
