ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'single' CHECK(kind IN ('single','multi','order'));
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS snippet TEXT;
ALTER TABLE quiz_questions ADD COLUMN IF NOT EXISTS boss BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS quiz_questions_pool_idx ON quiz_questions (level, topic, active);
