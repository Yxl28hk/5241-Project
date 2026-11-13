"""Courses SQL operations; callers own commit/rollback."""


def search_courses(db, query, category):
    # The quiz anchor course lives in this table but is never a browsable course.
    conditions, params = ["resource_type <> 'quiz'"], []
    if query:
        conditions.append("(title LIKE %s OR description LIKE %s OR author LIKE %s)")
        params.extend([f"%{query}%"] * 3)
    if category and category != "全部":
        conditions.append("category = %s")
        params.append(category)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return db.execute(
        f"SELECT * FROM courses {where} ORDER BY created_at DESC, id DESC", params
    ).fetchall()


def find_author(db, params):
    return db.execute("SELECT name FROM users WHERE id = %s", params).fetchone()


def insert_course(db, params):
    return db.execute(
        """INSERT INTO courses
        (title, category, resource_type, description, author, duration, cover, badge, filename, owner_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id""",
        params,
    )


def find_created_course(db, params):
    return db.execute("SELECT * FROM courses WHERE id = %s", params).fetchone()


def find_manager_role(db, params):
    return db.execute("SELECT role FROM users WHERE id = %s", params).fetchone()


def list_all_courses(db):
    return db.execute(
        "SELECT * FROM courses WHERE resource_type <> 'quiz' ORDER BY created_at DESC, id DESC"
    ).fetchall()


def list_owned_courses(db, params):
    return db.execute(
        "SELECT * FROM courses WHERE owner_id = %s ORDER BY created_at DESC, id DESC",
        params,
    ).fetchall()


def list_learners(db, params):
    return db.execute(
        """SELECT u.id, u.name, l.progress, l.started_at AS enrolled_at, l.last_opened_at, l.updated_at
        FROM learning_records l JOIN users u ON u.id = l.user_id
        WHERE l.course_id = %s ORDER BY l.updated_at DESC""",
        params,
    ).fetchall()


def delete_learner(db, params):
    return db.execute(
        "DELETE FROM learning_records WHERE course_id = %s AND user_id = %s", params
    )


def find_deletion_role(db, params):
    return db.execute("SELECT role FROM users WHERE id = %s", params).fetchone()


def find_course_file(db, params):
    return db.execute("SELECT filename FROM courses WHERE id = %s", params).fetchone()


def find_owned_course_file(db, params):
    return db.execute(
        "SELECT filename FROM courses WHERE id = %s AND owner_id = %s", params
    ).fetchone()


def delete_course_learning(db, params):
    return db.execute("DELETE FROM learning_records WHERE course_id = %s", params)


def delete_course(db, params):
    return db.execute("DELETE FROM courses WHERE id = %s", params)


def delete_owned_course(db, params):
    return db.execute("DELETE FROM courses WHERE id = %s AND owner_id = %s", params)


def count_learners(db, params):
    return db.execute(
        "SELECT COUNT(*) AS count FROM learning_records WHERE course_id = %s", params
    ).fetchone()


def find_actor_role(db, params):
    return db.execute("SELECT role FROM users WHERE id = %s", params).fetchone()


def find_course(db, params):
    return db.execute("SELECT * FROM courses WHERE id = %s", params).fetchone()


def find_owned_course(db, params):
    return db.execute(
        "SELECT * FROM courses WHERE id = %s AND owner_id = %s", params
    ).fetchone()


def learner_detail(db, course_id, user_id):
    return db.execute("""SELECT u.id,u.name,l.progress,l.started_at AS enrolled_at,l.last_opened_at,l.updated_at
        FROM learning_records l JOIN users u ON u.id=l.user_id
        WHERE l.course_id=%s AND l.user_id=%s""",(course_id,user_id)).fetchone()


def learner_exercises(db, course_id, user_id):
    return db.execute("""SELECT question_version,choice_id,correct,attempts,updated_at
        FROM lesson_exercise_results WHERE course_id=%s AND user_id=%s ORDER BY updated_at DESC""",(course_id,user_id)).fetchall()
