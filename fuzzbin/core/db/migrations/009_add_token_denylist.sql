-- Add token denylist for JWT revocation
-- Version: 009
-- Description: Create revoked_tokens table for token invalidation support

-- Revoked tokens table for JWT invalidation
-- Used to invalidate tokens on logout, password change, etc.
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti TEXT PRIMARY KEY,  -- JWT token ID (unique identifier)
    user_id INTEGER NOT NULL,  -- User who owned the token
    revoked_at TEXT NOT NULL DEFAULT (datetime('now')),  -- When token was revoked
    expires_at TEXT NOT NULL,  -- When token would have expired (for cleanup)
    reason TEXT,  -- Optional reason for revocation
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Index for efficient cleanup of expired revoked tokens
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_expires_at ON revoked_tokens(expires_at);

-- Index for revoking all tokens for a user
CREATE INDEX IF NOT EXISTS idx_revoked_tokens_user_id ON revoked_tokens(user_id);
