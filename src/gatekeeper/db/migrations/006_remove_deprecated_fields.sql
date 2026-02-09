-- Migration: Remove deprecated fields from domain-based access control overhaul
-- This migration removes is_public from apps, notify_private_app_requests from users,
-- and drops the app_access_requests table

-- Drop app_access_requests table (access requests are no longer used)
DROP TABLE IF EXISTS app_access_requests;

-- For PostgreSQL, we would use:
-- ALTER TABLE apps DROP COLUMN IF EXISTS is_public;
-- ALTER TABLE users DROP COLUMN IF EXISTS notify_private_app_requests;

-- For SQLite, column removal requires table recreation.
-- However, SQLite 3.35.0+ supports DROP COLUMN.
-- We'll use conditional logic based on what's supported.

-- Remove is_public column from apps (SQLite 3.35.0+)
ALTER TABLE apps DROP COLUMN is_public;

-- Remove notify_private_app_requests column from users (SQLite 3.35.0+)
ALTER TABLE users DROP COLUMN notify_private_app_requests;
