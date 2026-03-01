-- Migration 007: Add notify_new_registrations column to users table
-- This allows super-admins to opt-in for email notifications when new users register

ALTER TABLE users ADD COLUMN notify_new_registrations BOOLEAN DEFAULT FALSE;
