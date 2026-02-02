-- Add roles field to apps table
-- Stores a comma-separated list of allowed roles for the app
-- Default: "admin,user"

ALTER TABLE apps ADD COLUMN roles TEXT DEFAULT 'admin,user';
