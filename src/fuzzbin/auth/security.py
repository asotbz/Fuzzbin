"""Security utilities for password hashing and JWT token management."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt
import structlog

logger = structlog.get_logger(__name__)

# Default password hash for 'changeme' - used to detect if password hasn't been changed
# Generated with: bcrypt.hashpw(b'changeme', bcrypt.gensalt(rounds=12))
DEFAULT_PASSWORD_HASH = "$2b$12$7TBJrDjfUukBIYBrrLaBiecdSJKLXGbkJHvzNT.j9PAsAvbLJaG1S"


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
    to_encode.update({
        "exp": expire,
        "type": "access",
    })
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 10080,  # 7 days
) -> str:
    """
    Create a JWT refresh token.

    Refresh tokens have a longer expiration and are used to obtain new access tokens.

    Args:
        data: Payload data to encode in the token
        secret_key: Secret key for signing the token
        algorithm: JWT signing algorithm (default: HS256)
        expires_minutes: Token expiration time in minutes (default: 10080 = 7 days)

    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
    })
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def decode_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
    expected_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string to decode
        secret_key: Secret key used to sign the token
        algorithm: JWT signing algorithm (default: HS256)
        expected_type: If provided, validate token type matches ("access" or "refresh")

    Returns:
        Decoded token payload dict, or None if invalid/expired

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
        
        return payload
    except JWTError as e:
        logger.debug("token_decode_error", error=str(e))
        return None
