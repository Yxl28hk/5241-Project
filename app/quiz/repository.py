"""Quiz SQL operations; callers own commit/rollback.

Quiz answers reuse lesson_exercise_results and runs reuse mission_attempts, both
keyed by an explicit mission_id so Release Rescue history stays untouched.
"""

from app.learning.repository import upsert_exercise_result


def find_anchor_course(db):
    return db.execute(
        "SELECT id FROM courses WHERE resource_type = 'quiz' ORDER BY id LIMIT 1"
    ).fetchone()


def insert_anchor_course(db, params):
    return db.execute(
        """INSERT INTO courses
        (title, category, resource_type, description, author, duration, cover, badge)
        VALUES (%s, '技术', 'quiz', %s, '知行软件工程实验室', %s, 'tech', '水平摸底')
        RETURNING id""",
        params,
    ).fetchone()


def upsert_question(db, params):
    return db.execute(
        """INSERT INTO quiz_questions
        (code, version, level, topic, difficulty, stem, snippet, kind, boss, choices,
         correct_choice_id, explanation, explanations, source)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (code) DO UPDATE SET version = EXCLUDED.version,
            level = EXCLUDED.level, topic = EXCLUDED.topic,
            difficulty = EXCLUDED.difficulty, stem = EXCLUDED.stem,
            snippet = EXCLUDED.snippet, kind = EXCLUDED.kind, boss = EXCLUDED.boss,
            choices = EXCLUDED.choices, correct_choice_id = EXCLUDED.correct_choice_id,
            explanation = EXCLUDED.explanation, explanations = EXCLUDED.explanations,
            active = TRUE
        WHERE quiz_questions.source = 'seed'""",
        params,
    )


def list_active_questions(db):
    return db.execute(
        """SELECT code, version, level, topic, difficulty, stem, snippet, kind, boss,
            choices, correct_choice_id, explanation, explanations, source
           FROM quiz_questions WHERE active = TRUE ORDER BY level, code"""
    ).fetchall()


def list_questions(db):
    """Whole bank for the admin screen: inactive rows and the source included."""
    return db.execute(
        """SELECT code, version, level, topic, difficulty, stem, snippet, kind, boss,
            choices, correct_choice_id, explanation, explanations, source, active,
            created_at FROM quiz_questions ORDER BY level, code"""
    ).fetchall()


def find_question(db, params):
    return db.execute(
        """SELECT code, version, level, topic, difficulty, stem, snippet, kind, boss,
            choices, correct_choice_id, explanation, explanations, source, active,
            created_at FROM quiz_questions WHERE code = %s""",
        params,
    ).fetchone()


def count_question_answers(db, params):
    """Answered copies block deletion; see service.delete_question."""
    return db.execute(
        """SELECT count(*) AS hits FROM lesson_exercise_results
            WHERE question_version = %s""",
        params,
    ).fetchone()


def insert_question(db, params):
    return db.execute(
        """INSERT INTO quiz_questions
        (code, version, level, topic, difficulty, stem, snippet, kind, boss, choices,
         correct_choice_id, explanation, explanations, source, active)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING code""",
        params,
    ).fetchone()


def update_question(db, params):
    """Content only: code, version and source stay put so history and seed align."""
    return db.execute(
        """UPDATE quiz_questions SET level = %s, topic = %s, difficulty = %s,
            stem = %s, snippet = %s, kind = %s, boss = %s, choices = %s,
            correct_choice_id = %s, explanation = %s, explanations = %s
           WHERE code = %s RETURNING code""",
        params,
    ).fetchone()


def set_question_active(db, params):
    return db.execute(
        "UPDATE quiz_questions SET active = %s WHERE code = %s RETURNING code",
        params,
    ).fetchone()


def delete_question(db, params):
    return db.execute(
        "DELETE FROM quiz_questions WHERE code = %s RETURNING code",
        params,
    ).fetchone()


def find_revenge_versions(db, params):
    """Wrong answers become the revenge pool; answering correctly removes them."""
    return db.execute(
        """SELECT question_version FROM lesson_exercise_results
            WHERE user_id = %s AND course_id = %s AND correct = FALSE""",
        params,
    ).fetchall()


def find_owned_run(db, params):
    """The run id alone decides the mode, so match every quiz mission id."""
    return db.execute(
        """SELECT * FROM mission_attempts
            WHERE id = %s AND user_id = %s AND mission_id = ANY(%s)""",
        params,
    ).fetchone()


def find_unfinished_run(db, params):
    return db.execute(
        """SELECT * FROM mission_attempts WHERE user_id = %s AND mission_id = %s
            AND step < %s ORDER BY id DESC LIMIT 1""",
        params,
    ).fetchone()


def insert_run(db, params):
    return db.execute(
        """INSERT INTO mission_attempts (user_id, mission_id, answers)
            VALUES (%s, %s, %s) RETURNING *""",
        params,
    ).fetchone()


def advance_run(db, params):
    return db.execute(
        """UPDATE mission_attempts SET step = step + 1, score = score + %s, answers = %s
            WHERE id = %s AND user_id = %s AND step = %s RETURNING *""",
        params,
    ).fetchone()


def finish_run(db, params):
    return db.execute(
        """UPDATE mission_attempts SET step = %s, score = %s, answers = %s
            WHERE id = %s AND user_id = %s AND step < %s RETURNING *""",
        params,
    ).fetchone()


def find_best_run_score(db, params):
    return db.execute(
        """SELECT MAX(score) AS score FROM mission_attempts
            WHERE user_id = %s AND mission_id = %s AND step = %s""",
        params,
    ).fetchone()


def find_latest_finished_run(db, params):
    return db.execute(
        """SELECT * FROM mission_attempts WHERE user_id = %s AND mission_id = %s
            AND step = %s ORDER BY id DESC LIMIT 1""",
        params,
    ).fetchone()


def list_finished_runs(db, params):
    return db.execute(
        """SELECT score, answers FROM mission_attempts
            WHERE user_id = %s AND mission_id = %s AND step = %s ORDER BY id DESC""",
        params,
    ).fetchall()


def record_answer(db, params):
    """Persist one question result; reuses the shared lesson_exercise_results table."""
    return upsert_exercise_result(db, params)


def find_profile_reference(db, params):
    return db.execute(
        """SELECT quiz_best_score, quiz_badge, quiz_level, quiz_topic_scores,
            quiz_updated_at FROM learning_profiles WHERE user_id = %s""",
        params,
    ).fetchone()


def upsert_profile_reference(db, params):
    return db.execute(
        """INSERT INTO learning_profiles (user_id, quiz_best_score, quiz_badge,
                quiz_level, quiz_topic_scores, quiz_updated_at)
            VALUES (%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                quiz_best_score = EXCLUDED.quiz_best_score,
                quiz_badge = EXCLUDED.quiz_badge,
                quiz_level = EXCLUDED.quiz_level,
                quiz_topic_scores = EXCLUDED.quiz_topic_scores,
                quiz_updated_at = CURRENT_TIMESTAMP""",
        params,
    )


def delete_user_runs(db, params):
    """Wipe every quiz run for one student.

    Runs are what make a level show 已通关, so a reset has to remove them.
    Release Rescue keeps its own mission_id and is never touched.
    """
    return db.execute(
        "DELETE FROM mission_attempts WHERE user_id = %s AND mission_id = ANY(%s)",
        params,
    )


def delete_user_results(db, params):
    """Drop the answers that feed the revenge pool, scoped to the anchor course."""
    return db.execute(
        "DELETE FROM lesson_exercise_results WHERE user_id = %s AND course_id = %s",
        params,
    )


def count_user_progress(db, params):
    """How much quest data a student really has, so the UI can offer a reset.

    The profile reference can be null while runs and answers still exist (after
    a reset, or when only quick/revenge was played), so the button cannot be
    driven by the reference alone.
    """
    return db.execute(
        """SELECT
            (SELECT count(*) FROM mission_attempts
              WHERE user_id = %s AND mission_id = ANY(%s)) AS runs,
            (SELECT count(*) FROM lesson_exercise_results
              WHERE user_id = %s AND course_id = %s) AS answers""",
        params,
    ).fetchone()


def clear_profile_reference(db, params):
    return db.execute(
        """UPDATE learning_profiles SET quiz_best_score = NULL, quiz_badge = NULL,
            quiz_level = NULL, quiz_topic_scores = NULL, quiz_updated_at = NULL
            WHERE user_id = %s""",
        params,
    )


def adopt_profile_level(db, params):
    """Only ever called after the student explicitly accepts the quiz suggestion."""
    return db.execute(
        """INSERT INTO learning_profiles (user_id, level) VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET level = EXCLUDED.level,
                updated_at = CURRENT_TIMESTAMP""",
        params,
    )
