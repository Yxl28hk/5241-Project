"""Missions SQL operations; callers own commit/rollback."""


def find_unfinished_attempt(db, params):
    return db.execute(
        """SELECT * FROM mission_attempts WHERE user_id = %s AND mission_id = %s
            AND step < %s ORDER BY id DESC LIMIT 1""",
        params,
    ).fetchone()


def insert_attempt(db, params):
    return db.execute(
        "INSERT INTO mission_attempts (user_id, mission_id) VALUES (%s, %s) RETURNING *",
        params,
    ).fetchone()


def find_owned_attempt(db, params):
    return db.execute(
        "SELECT * FROM mission_attempts WHERE id = %s AND user_id = %s", params
    ).fetchone()


def advance_attempt(db, params):
    return db.execute(
        """UPDATE mission_attempts SET step = step + 1, score = score + %s, answers = %s
            WHERE id = %s AND user_id = %s AND step = %s RETURNING *""",
        params,
    ).fetchone()


def find_latest_mission(db, params):
    return db.execute(
        """SELECT * FROM mission_attempts WHERE user_id = %s AND mission_id = %s
            ORDER BY id DESC LIMIT 1""",
        params,
    ).fetchone()


def find_best_mission_score(db, params):
    return db.execute(
        """SELECT MAX(score) AS score FROM mission_attempts
            WHERE user_id = %s AND mission_id = %s AND step = %s""",
        params,
    ).fetchone()
