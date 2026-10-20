CREATE TABLE IF NOT EXISTS lesson_notebooks (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        course_id BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        notes TEXT NOT NULL DEFAULT '', task_draft TEXT NOT NULL DEFAULT '', revision INTEGER NOT NULL DEFAULT 1,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id, course_id));

CREATE TABLE IF NOT EXISTS lesson_exercise_results (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        course_id BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE, question_version TEXT NOT NULL,
        choice_id TEXT NOT NULL, correct BOOLEAN NOT NULL, attempts INTEGER NOT NULL DEFAULT 1,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, course_id, question_version));

CREATE TABLE IF NOT EXISTS lesson_conversations (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        course_id BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
        token TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, messages JSONB NOT NULL DEFAULT '[]',
        last_request_id TEXT, last_fingerprint TEXT, last_reply JSONB,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id, course_id));
