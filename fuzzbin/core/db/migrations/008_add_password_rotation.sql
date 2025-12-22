-- Add password rotation enforcement
-- Version: 008
-- Description: Add password_must_change flag to enforce password rotation for seeded admin user

-- Add password_must_change column to users table
ALTER TABLE users ADD COLUMN password_must_change INTEGER DEFAULT 0 NOT NULL CHECK (password_must_change IN (0, 1));

-- Force admin user to change password on next login
-- This applies to both new installations and existing ones with default password
UPDATE users SET password_must_change = 1 WHERE username = 'admin';
