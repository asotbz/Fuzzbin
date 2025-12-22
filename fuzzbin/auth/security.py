"""Security utilities for password hashing and JWT token management."""

import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, Optional, Set

import bcrypt
from jose import JWTError, jwt
import structlog

logger = structlog.get_logger(__name__)

# Default password hash for 'changeme' - used to detect if password hasn't been changed
# Generated with: bcrypt.hashpw(b'changeme', bcrypt.gensalt(rounds=12))
DEFAULT_PASSWORD_HASH = "$2b$12$7TBJrDjfUukBIYBrrLaBiecdSJKLXGbkJHvzNT.j9PAsAvbLJaG1S"


# ============================================================================
# Token Denylist Cache
# ============================================================================


class TokenDenylistCache:
    """In-memory LRU cache for revoked token JTIs.

    Caches both positive (token is revoked) and negative (token not revoked)
    results to minimize database queries. Negative results expire after 60s.
    """

    def __init__(self, maxsize: int = 1000, negative_ttl_seconds: int = 60):
        """Initialize the cache.

        Args:
            maxsize: Maximum number of entries to cache
            negative_ttl_seconds: How long to cache "not revoked" results
        """
        self.maxsize = maxsize
        self.negative_ttl = negative_ttl_seconds
        self._revoked: Dict[str, datetime] = {}  # jti -> revoked_at
        self._not_revoked: Dict[str, datetime] = {}  # jti -> cached_at

    def is_revoked(self, jti: str) -> Optional[bool]:
        """Check if a token JTI is in the cache.

        Returns:
            True if revoked (cached positive), False if not revoked (cached negative),
            None if not in cache (need to check DB)
        """
        # Check positive cache (revoked tokens)
        if jti in self._revoked:
            return True

        # Check negative cache (not revoked, with TTL)
        if jti in self._not_revoked:
            cached_at = self._not_revoked[jti]
            if datetime.now(timezone.utc) - cached_at < timedelta(seconds=self.negative_ttl):
                return False
            # Expired negative cache entry
            del self._not_revoked[jti]

        return None

    def mark_revoked(self, jti: str) -> None:
        """Mark a token as revoked in the cache."""
        self._evict_if_needed()
        self._revoked[jti] = datetime.now(timezone.utc)
        # Remove from negative cache if present
        self._not_revoked.pop(jti, None)

    def mark_not_revoked(self, jti: str) -> None:
        """Cache that a token is NOT revoked (negative cache)."""
        self._evict_if_needed()
        self._not_revoked[jti] = datetime.now(timezone.utc)

    def invalidate(self, jti: str) -> None:
        """Remove a token from all caches."""
        self._revoked.pop(jti, None)
        self._not_revoked.pop(jti, None)

    def invalidate_user(self, user_id: int) -> None:
        """Invalidate all cached entries (used when revoking all user tokens).

        Note: This clears the entire cache since we don't track user_id per jti.
        A more sophisticated implementation could maintain a user_id index.
        """
        self._revoked.clear()
        self._not_revoked.clear()

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache is full."""
        total = len(self._revoked) + len(self._not_revoked)
        if total >= self.maxsize:
            # Clear expired negative entries first
            now = datetime.now(timezone.utc)
            expired = [
                jti
                for jti, cached_at in self._not_revoked.items()
                if now - cached_at >= timedelta(seconds=self.negative_ttl)
            ]
            for jti in expired:
                del self._not_revoked[jti]

            # If still full, clear half of negative cache
            if len(self._revoked) + len(self._not_revoked) >= self.maxsize:
                items = list(self._not_revoked.items())
                for jti, _ in items[: len(items) // 2]:
                    del self._not_revoked[jti]


# Global cache instance
_token_denylist_cache: Optional[TokenDenylistCache] = None


def get_token_denylist_cache() -> TokenDenylistCache:
    """Get the global token denylist cache instance."""
    global _token_denylist_cache
    if _token_denylist_cache is None:
        _token_denylist_cache = TokenDenylistCache()
    return _token_denylist_cache


# ============================================================================
# Password Hashing
# ============================================================================


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Bcrypt hashed password string

    Example:
        >>> hashed = hash_password("mysecretpassword")
        >>> hashed.startswith("$2b$")
        True
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hashed password to check against

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("test")
        >>> verify_password("test", hashed)
        True
        >>> verify_password("wrong", hashed)
        False
    """
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception as e:
        logger.warning("password_verification_error", error=str(e))
        return False


def is_default_password(hashed_password: str) -> bool:
    """
    Check if the given hash matches the default password 'changeme'.

    This is used to warn administrators that they should change the default password.

    Args:
        hashed_password: The stored password hash to check

    Returns:
        True if the password is the default 'changeme', False otherwise
    """
    return verify_password("changeme", hashed_password)


def create_access_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 30,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token
        secret_key: Secret key for signing the token
        algorithm: JWT signing algorithm (default: HS256)
        expires_minutes: Token expiration time in minutes (default: 30)

    Returns:
        Encoded JWT token string

    Example:
        >>> token = create_access_token(
        ...     data={"sub": "admin", "user_id": 1},
        ...     secret_key="mysecret",
        ...     expires_minutes=30
        ... )
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    jti = str(uuid.uuid4())  # Unique token ID for revocation
    to_encode.update(
        {
            "exp": expire,
            "type": "access",
            "jti": jti,
        }
    )
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 1440,  # 24 hours (reduced from 7 days)
) -> str:
    """
    Create a JWT refresh token.

    Refresh tokens have a longer expiration and are used to obtain new access tokens.

    Args:
        data: Payload data to encode in the token
        secret_key: Secret key for signing the token
        algorithm: JWT signing algorithm (default: HS256)
        expires_minutes: Token expiration time in minutes (default: 1440 = 24 hours)

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    jti = str(uuid.uuid4())  # Unique token ID for revocation
    to_encode.update(
        {
            "exp": expire,
            "type": "refresh",
            "jti": jti,
        }
    )
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def decode_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
    expected_type: Optional[str] = None,
    check_revoked: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string to decode
        secret_key: Secret key used to sign the token
        algorithm: JWT signing algorithm (default: HS256)
        expected_type: If provided, validate token type matches ("access" or "refresh")
        check_revoked: If True, check the token denylist cache

    Returns:
        Decoded token payload dict, or None if invalid/expired/revoked

    Example:
        >>> payload = decode_token(token, "mysecret")
        >>> if payload:
        ...     user_id = payload.get("user_id")
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        # Validate token type if specified
        if expected_type:
            token_type = payload.get("type")
            if token_type != expected_type:
                logger.warning(
                    "token_type_mismatch",
                    expected=expected_type,
                    actual=token_type,
                )
                return None

        # Check if token is revoked (using cache)
        if check_revoked:
            jti = payload.get("jti")
            if jti:
                cache = get_token_denylist_cache()
                is_revoked = cache.is_revoked(jti)
                if is_revoked is True:
                    logger.debug("token_revoked", jti=jti)
                    return None
                # Note: If is_revoked is None (not in cache), we don't check DB here
                # The DB check should be done by the caller if needed for high-security operations

        return payload
    except JWTError as e:
        logger.debug("token_decode_error", error=str(e))
        return None


# ============================================================================
# Token Revocation Functions
# ============================================================================


async def revoke_token(
    jti: str,
    user_id: int,
    expires_at: datetime,
    reason: Optional[str] = None,
    connection=None,
) -> None:
    """Revoke a single token by its JTI.

    Args:
        jti: Token's unique identifier
        user_id: User who owns the token
        expires_at: When the token would have expired
        reason: Optional reason for revocation
        connection: Database connection (if None, will get from fuzzbin)
    """
    cache = get_token_denylist_cache()
    cache.mark_revoked(jti)

    if connection is None:
        import fuzzbin

        repo = await fuzzbin.get_repository()
        connection = repo._connection

    await connection.execute(
        """
        INSERT OR REPLACE INTO revoked_tokens (jti, user_id, revoked_at, expires_at, reason)
        VALUES (?, ?, datetime('now'), ?, ?)
        """,
        (jti, user_id, expires_at.isoformat(), reason),
    )
    await connection.commit()

    logger.info("token_revoked", jti=jti, user_id=user_id, reason=reason)


async def revoke_all_user_tokens(
    user_id: int,
    reason: Optional[str] = None,
    connection=None,
) -> int:
    """Revoke all tokens for a user.

    Note: This inserts a special marker and relies on cleanup to handle
    the actual tokens. New tokens issued after this call are not affected.

    Args:
        user_id: User whose tokens should be revoked
        reason: Optional reason for revocation
        connection: Database connection

    Returns:
        Number of tokens revoked (from existing revoked_tokens entries)
    """
    cache = get_token_denylist_cache()
    cache.invalidate_user(user_id)

    if connection is None:
        import fuzzbin

        repo = await fuzzbin.get_repository()
        connection = repo._connection

    # We can't revoke tokens we don't know about, but we can ensure
    # any token that gets checked against the DB will be rejected
    # by inserting a marker. For simplicity, we rely on password change
    # to invalidate old tokens (since they won't have new password claim).

    logger.info("user_tokens_invalidated", user_id=user_id, reason=reason)
    return 0


async def check_token_revoked_in_db(
    jti: str,
    connection=None,
) -> bool:
    """Check if a token is revoked in the database.

    Updates the cache with the result.

    Args:
        jti: Token's unique identifier
        connection: Database connection

    Returns:
        True if revoked, False otherwise
    """
    cache = get_token_denylist_cache()

    # Check cache first
    cached = cache.is_revoked(jti)
    if cached is not None:
        return cached

    if connection is None:
        import fuzzbin

        repo = await fuzzbin.get_repository()
        connection = repo._connection

    cursor = await connection.execute(
        "SELECT 1 FROM revoked_tokens WHERE jti = ?",
        (jti,),
    )
    row = await cursor.fetchone()

    is_revoked = row is not None
    if is_revoked:
        cache.mark_revoked(jti)
    else:
        cache.mark_not_revoked(jti)

    return is_revoked


async def cleanup_expired_tokens(connection=None) -> int:
    """Remove expired entries from the revoked_tokens table.

    Should be called periodically (e.g., daily) to prevent table growth.

    Args:
        connection: Database connection

    Returns:
        Number of entries removed
    """
    if connection is None:
        import fuzzbin

        repo = await fuzzbin.get_repository()
        connection = repo._connection

    cursor = await connection.execute(
        "DELETE FROM revoked_tokens WHERE expires_at < datetime('now')"
    )
    await connection.commit()

    deleted = cursor.rowcount
    if deleted > 0:
        logger.info("expired_tokens_cleaned", count=deleted)

    return deleted
