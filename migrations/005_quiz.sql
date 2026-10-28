CREATE TABLE IF NOT EXISTS quiz_questions (
            code TEXT PRIMARY KEY,
            version TEXT NOT NULL UNIQUE,
            level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 3),
            topic TEXT NOT NULL CHECK(topic IN ('concepts','ai-assistant','soft-skills','process')),
            difficulty INTEGER NOT NULL CHECK(difficulty BETWEEN 1 AND 3),
            stem TEXT NOT NULL,
            choices JSONB NOT NULL,
            correct_choice_id TEXT NOT NULL,
            explanation TEXT NOT NULL,
            explanations JSONB NOT NULL DEFAULT '{}',
            source TEXT NOT NULL DEFAULT 'seed',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

CREATE INDEX IF NOT EXISTS quiz_questions_level_idx ON quiz_questions (level, active);

ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS quiz_best_score INTEGER;
ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS quiz_badge TEXT;
ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS quiz_level TEXT;
ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS quiz_topic_scores JSONB;
ALTER TABLE learning_profiles ADD COLUMN IF NOT EXISTS quiz_updated_at TIMESTAMPTZ;
