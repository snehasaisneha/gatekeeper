-- Add attempts column to OTPs table for rate limiting verification attempts
-- Each OTP gets 5 attempts before being invalidated

ALTER TABLE otps ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
