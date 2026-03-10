-- Add session metadata for investigation and revocation workflows

ALTER TABLE sessions ADD COLUMN auth_method TEXT;
ALTER TABLE sessions ADD COLUMN ip_address TEXT;
ALTER TABLE sessions ADD COLUMN user_agent TEXT;
ALTER TABLE sessions ADD COLUMN last_seen_at TIMESTAMP;

UPDATE sessions
SET last_seen_at = created_at
WHERE last_seen_at IS NULL;
