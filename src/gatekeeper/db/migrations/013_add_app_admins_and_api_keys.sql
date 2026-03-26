ALTER TABLE user_app_access
ADD COLUMN is_app_admin BOOLEAN NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS app_api_keys (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL REFERENCES apps(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    key_prefix TEXT NOT NULL UNIQUE,
    key_hash TEXT NOT NULL UNIQUE,
    created_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_by_email TEXT,
    last_used_at TIMESTAMP,
    revoked_at TIMESTAMP,
    revoked_by TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_api_keys_app_id ON app_api_keys(app_id);
