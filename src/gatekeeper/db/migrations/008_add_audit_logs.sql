-- Migration 008: Add audit_logs table for tracking auth and admin events

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),

    -- Who performed the action
    actor_id TEXT,
    actor_email TEXT,

    -- What happened
    event_type TEXT NOT NULL,

    -- What was affected (optional)
    target_type TEXT,
    target_id TEXT,

    -- Request context
    ip_address TEXT,
    user_agent TEXT,

    -- Flexible details (JSON)
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_id ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_target ON audit_logs(target_type, target_id);
