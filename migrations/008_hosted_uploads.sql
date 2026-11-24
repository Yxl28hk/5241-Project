CREATE TABLE IF NOT EXISTS uploaded_assets (
    filename TEXT PRIMARY KEY,
    content BYTEA NOT NULL,
    content_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS studio_ai_jobs (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    request_id TEXT NOT NULL,
    state TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    cancelled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(owner, request_id)
);
CREATE INDEX IF NOT EXISTS studio_ai_jobs_created ON studio_ai_jobs(created_at);
