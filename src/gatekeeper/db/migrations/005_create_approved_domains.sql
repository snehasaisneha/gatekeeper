-- Migration: Create approved_domains table for domain-based access control
-- This table stores email domains that are considered "internal"
-- Users with emails from these domains are auto-approved and have access to ALL apps

CREATE TABLE IF NOT EXISTS approved_domains (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    created_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_approved_domains_domain ON approved_domains(domain);
