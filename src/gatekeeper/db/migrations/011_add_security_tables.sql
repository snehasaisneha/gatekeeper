-- Migration 011: Add security tables for IP and email banning

-- Banned IP addresses table
CREATE TABLE IF NOT EXISTS banned_ips (
    id TEXT PRIMARY KEY,
    ip_address TEXT NOT NULL,
    reason TEXT NOT NULL,
    details TEXT,
    banned_at TEXT NOT NULL DEFAULT (datetime('now')),
    banned_by TEXT,
    expires_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    associated_email TEXT
);

CREATE INDEX IF NOT EXISTS idx_banned_ips_ip_address ON banned_ips(ip_address);
CREATE INDEX IF NOT EXISTS idx_banned_ips_is_active ON banned_ips(is_active);
CREATE INDEX IF NOT EXISTS idx_banned_ips_expires_at ON banned_ips(expires_at);

-- Banned email addresses/patterns table
CREATE TABLE IF NOT EXISTS banned_emails (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    is_pattern INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL,
    details TEXT,
    banned_at TEXT NOT NULL DEFAULT (datetime('now')),
    banned_by TEXT,
    expires_at TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    associated_ip TEXT
);

CREATE INDEX IF NOT EXISTS idx_banned_emails_email ON banned_emails(email);
CREATE INDEX IF NOT EXISTS idx_banned_emails_is_active ON banned_emails(is_active);
CREATE INDEX IF NOT EXISTS idx_banned_emails_is_pattern ON banned_emails(is_pattern);
CREATE INDEX IF NOT EXISTS idx_banned_emails_expires_at ON banned_emails(expires_at);
