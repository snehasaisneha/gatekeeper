-- Migration 010: Add notify_all_registrations column to users table
-- This allows super-admins to opt-in for email notifications when ANY new user registers
-- (including auto-approved users from accepted domains)

ALTER TABLE users ADD COLUMN notify_all_registrations BOOLEAN DEFAULT FALSE;
