"""Authentication module for Fuzzbin API."""

from .security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    DEFAULT_PASSWORD_HASH,
    is_default_password,
)
from .schemas import (
    LoginRequest,
    TokenResponse,
    PasswordChangeRequest,
    RefreshRequest,
    UserInfo,
)
from .throttle import LoginThrottle, get_login_throttle

__all__ = [
    # Security functions
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "DEFAULT_PASSWORD_HASH",
    "is_default_password",
    # Schemas
    "LoginRequest",
    "TokenResponse",
    "PasswordChangeRequest",
    "RefreshRequest",
    "UserInfo",
    # Throttle
    "LoginThrottle",
    "get_login_throttle",
]
