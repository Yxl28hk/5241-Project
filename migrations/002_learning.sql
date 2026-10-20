CREATE TABLE IF NOT EXISTS learning_profiles (
        user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        goal TEXT NOT NULL DEFAULT '', level TEXT NOT NULL DEFAULT '',
        weekly_hours INTEGER CHECK(weekly_hours BETWEEN 1 AND 40),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP);

CREATE TABLE IF NOT EXISTS learner_preferences (
        user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
        active_path_slug TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS learning_path_positions (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        path_slug TEXT NOT NULL, course_id BIGINT REFERENCES courses(id) ON DELETE SET NULL,
        opened_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, path_slug));

ALTER TABLE learning_records ADD COLUMN IF NOT EXISTS last_opened_at TIMESTAMPTZ;
