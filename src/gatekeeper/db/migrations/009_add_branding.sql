-- Branding settings for whitelabeling
-- Single-row table enforced by CHECK constraint

CREATE TABLE IF NOT EXISTS branding (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    logo_url TEXT,
    logo_square_url TEXT,
    favicon_url TEXT,
    accent_color TEXT NOT NULL DEFAULT 'ink',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by TEXT
);

-- Insert default row
INSERT OR IGNORE INTO branding (id, accent_color) VALUES (1, 'ink');
