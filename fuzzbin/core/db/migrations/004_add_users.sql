-- Add users table for authentication
-- Version: 004
-- Description: Create users table with seeded admin user for single-user auth

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active INTEGER DEFAULT 1 NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT,
    CHECK (is_active IN (0, 1))
);

-- Create index on username for fast lookup
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Seed initial admin user with default password 'changeme'
-- SECURITY: Change this password immediately after first login!
-- Default password hash is for 'changeme' - generated with bcrypt
INSERT OR IGNORE INTO users (username, password_hash, is_active, created_at, updated_at)
VALUES (
    'admin',
    '$2b$12$7TBJrDjfUukBIYBrrLaBiecdSJKLXGbkJHvzNT.j9PAsAvbLJaG1S',
    1,
    datetime('now'),
    datetime('now')
);
