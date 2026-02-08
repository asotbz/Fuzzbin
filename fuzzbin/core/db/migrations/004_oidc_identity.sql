-- OIDC identity binding migration
-- Version: 004
-- Description: Add OIDC issuer and subject columns to users table for
--              single-user identity binding via OpenID Connect.

--------------------------------------------------------------------------------
-- ADD OIDC COLUMNS TO USERS TABLE
--------------------------------------------------------------------------------

-- Issuer URL from the OIDC provider's ID token (iss claim)
ALTER TABLE users ADD COLUMN oidc_issuer TEXT;

-- Subject identifier from the OIDC provider's ID token (sub claim)
ALTER TABLE users ADD COLUMN oidc_subject TEXT;

--------------------------------------------------------------------------------
-- UNIQUE INDEX ON OIDC IDENTITY
--------------------------------------------------------------------------------

-- Ensure a given iss+sub pair can only be bound to one local user.
-- Partial index: only applies when both columns are non-null.
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_oidc_identity
    ON users (oidc_issuer, oidc_subject)
    WHERE oidc_issuer IS NOT NULL AND oidc_subject IS NOT NULL;
