"""Learning SQL operations; callers own commit/rollback."""


def list_enrolled_courses(db, params):
    return db.execute(
        """SELECT c.*, l.progress FROM learning_records l
        JOIN courses c ON c.id = l.course_id
        WHERE l.user_id = %s ORDER BY l.updated_at DESC""",
        params,
    ).fetchall()


def find_course(db, params):
    return db.execute("SELECT id FROM courses WHERE id = %s", params).fetchone()


def upsert_enrollment(db, params):
    return db.execute(
        """INSERT INTO learning_records (user_id, course_id) VALUES (%s, %s)
        ON CONFLICT(user_id, course_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP""",
        params,
    )


def delete_enrollment(db, params):
    return db.execute(
        "DELETE FROM learning_records WHERE user_id = %s AND course_id = %s", params
    )


def upsert_profile(db, params):
    return db.execute(
        """INSERT INTO learning_profiles (user_id, goal, level, weekly_hours) VALUES (%s, %s, %s, %s)
            ON CONFLICT(user_id) DO UPDATE SET goal = EXCLUDED.goal, level = EXCLUDED.level,
            weekly_hours = EXCLUDED.weekly_hours, updated_at = CURRENT_TIMESTAMP""",
        params,
    )


def upsert_active_path(db, params):
    return db.execute(
        """INSERT INTO learner_preferences (user_id, active_path_slug) VALUES (%s, %s)
            ON CONFLICT(user_id) DO UPDATE SET active_path_slug = EXCLUDED.active_path_slug""",
        params,
    )


def find_lesson(db, params):
    return db.execute(
        """SELECT c.id, c.title, c.description, c.filename, c.duration, p.slug,
            COALESCE(l.progress, 0) AS progress, (l.user_id IS NOT NULL) AS enrolled, l.last_opened_at FROM courses c
            LEFT JOIN prototype_courses p ON p.course_id = c.id
            LEFT JOIN learning_records l ON l.course_id = c.id AND l.user_id = %s WHERE c.id = %s""",
        params,
    ).fetchone()


def find_exercise_result(db, params):
    return db.execute(
        "SELECT * FROM lesson_exercise_results WHERE user_id=%s AND course_id=%s AND question_version=%s",
        params,
    ).fetchone()


def upsert_exercise_result(db, params):
    return db.execute(
        """INSERT INTO lesson_exercise_results (user_id,course_id,question_version,choice_id,correct)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT(user_id,course_id,question_version) DO UPDATE
            SET choice_id=EXCLUDED.choice_id,correct=EXCLUDED.correct,attempts=lesson_exercise_results.attempts+1,
            updated_at=CURRENT_TIMESTAMP RETURNING *""",
        params,
    ).fetchone()


def insert_notebook(db, params):
    return db.execute(
        """INSERT INTO lesson_notebooks (user_id,course_id,notes,task_draft)
                VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING *""",
        params,
    ).fetchone()


def update_notebook_revision(db, params):
    return db.execute(
        """UPDATE lesson_notebooks SET notes=%s,task_draft=%s,revision=revision+1,updated_at=CURRENT_TIMESTAMP
                WHERE user_id=%s AND course_id=%s AND revision=%s RETURNING *""",
        params,
    ).fetchone()


def update_enrolled_progress(db, params):
    return db.execute(
        """UPDATE learning_records SET progress = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND course_id = %s RETURNING progress""",
        params,
    ).fetchone()


def find_course_context(db, params):
    return db.execute(
        """SELECT c.id,c.title,c.description,p.slug,COALESCE(l.progress,0) AS progress
        FROM courses c LEFT JOIN prototype_courses p ON p.course_id=c.id
        LEFT JOIN learning_records l ON l.course_id=c.id AND l.user_id=%s WHERE c.id=%s""",
        params,
    ).fetchone()


def find_profile(db, params):
    return db.execute(
        "SELECT goal, level, weekly_hours, updated_at FROM learning_profiles WHERE user_id = %s",
        params,
    ).fetchone()


def find_active_path(db, params):
    return db.execute(
        "SELECT active_path_slug FROM learner_preferences WHERE user_id = %s", params
    ).fetchone()


def list_lesson_progress(db, params):
    return db.execute(
        """SELECT p.slug, c.id, c.title, COALESCE(l.progress, 0) AS progress,
        l.last_opened_at, l.updated_at, (l.user_id IS NOT NULL) AS enrolled
        FROM prototype_courses p JOIN courses c ON c.id = p.course_id
        LEFT JOIN learning_records l ON l.course_id = c.id AND l.user_id = %s""",
        params,
    ).fetchall()


def find_path_position(db, params):
    return db.execute(
        """SELECT pos.course_id FROM learning_path_positions pos
        JOIN learning_records l ON l.user_id = pos.user_id AND l.course_id = pos.course_id
        WHERE pos.user_id = %s AND pos.path_slug = %s""",
        params,
    ).fetchone()


def update_last_visit(db, params):
    return db.execute(
        "UPDATE learning_records SET last_opened_at = CURRENT_TIMESTAMP WHERE user_id = %s AND course_id = %s",
        params,
    )


def find_visit_path(db, params):
    return db.execute(
        "SELECT active_path_slug FROM learner_preferences WHERE user_id = %s", params
    ).fetchone()


def find_lesson_slug(db, params):
    return db.execute(
        "SELECT slug FROM prototype_courses WHERE course_id = %s", params
    ).fetchone()


def upsert_path_position(db, params):
    return db.execute(
        """INSERT INTO learning_path_positions (user_id, path_slug, course_id) VALUES (%s, %s, %s)
            ON CONFLICT(user_id, path_slug) DO UPDATE SET course_id = EXCLUDED.course_id, opened_at = CURRENT_TIMESTAMP""",
        params,
    )


def find_notebook(db, params):
    return db.execute(
        "SELECT notes, task_draft, revision, updated_at FROM lesson_notebooks WHERE user_id=%s AND course_id=%s",
        params,
    ).fetchone()
