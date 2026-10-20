"""Tutor SQL operations; callers own commit/rollback."""


def reset_conversation_revision(db, params):
    return db.execute(
        """UPDATE lesson_conversations SET token=%s,revision=0,messages='[]',last_request_id=NULL,
            last_fingerprint=NULL,last_reply=NULL,updated_at=CURRENT_TIMESTAMP
            WHERE user_id=%s AND course_id=%s AND token=%s AND revision=%s RETURNING *""",
        params,
    ).fetchone()


def find_course_context(db, params):
    return db.execute(
        """SELECT c.id, c.title, c.description, p.slug, COALESCE(l.progress, 0) AS progress
            FROM courses c LEFT JOIN prototype_courses p ON p.course_id = c.id
            LEFT JOIN learning_records l ON l.course_id = c.id AND l.user_id = %s WHERE c.id = %s""",
        params,
    ).fetchone()


def find_token_conversation(db, params):
    return db.execute(
        "SELECT * FROM lesson_conversations WHERE user_id=%s AND course_id=%s AND token=%s",
        params,
    ).fetchone()


def save_conversation_revision(db, params):
    return db.execute(
        """UPDATE lesson_conversations SET messages=%s,revision=revision+1,last_request_id=%s,
            last_fingerprint=%s,last_reply=%s,updated_at=CURRENT_TIMESTAMP
            WHERE user_id=%s AND course_id=%s AND token=%s AND revision=%s RETURNING *""",
        params,
    ).fetchone()


def insert_conversation(db, params):
    return db.execute(
        """INSERT INTO lesson_conversations (user_id, course_id, token) VALUES (%s,%s,%s)
        ON CONFLICT(user_id,course_id) DO NOTHING""",
        params,
    )


def find_conversation(db, params):
    return db.execute(
        "SELECT * FROM lesson_conversations WHERE user_id=%s AND course_id=%s", params
    ).fetchone()
