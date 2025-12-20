"""Authentication routes for login, logout, password change, and token refresh."""

from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from fuzzbin.auth import (
    LoginRequest,
    TokenResponse,
    PasswordChangeRequest,
    RefreshRequest,
    UserInfo,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    get_login_throttle,
    LoginThrottle,
)
from fuzzbin.core.db import VideoRepository

from ..dependencies import get_repository, get_api_settings, require_auth
from ..settings import APISettings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user",
    responses={
        200: {"description": "Successful authentication"},
        401: {"description": "Invalid credentials"},
        429: {"description": "Too many failed attempts"},
    },
)
async def login(
    request: Request,
    login_request: LoginRequest,
    repo: VideoRepository = Depends(get_repository),
    settings: APISettings = Depends(get_api_settings),
    throttle: LoginThrottle = Depends(get_login_throttle),
) -> TokenResponse:
    """
    Authenticate a user and return JWT tokens.

    Validates username and password, returns access and refresh tokens
    on successful authentication.

    Rate limited: 5 failed attempts per minute per IP address.
    """
    client_ip = get_client_ip(request)

    # Check if IP is throttled
    if throttle.is_blocked(client_ip):
        retry_after = throttle.get_retry_after(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # Look up user
    cursor = await repo._connection.execute(
        "SELECT id, username, password_hash, is_active FROM users WHERE username = ?",
        (login_request.username,),
    )
    row = await cursor.fetchone()

    if not row:
        throttle.record_failure(client_ip)
        logger.warning("login_failed_user_not_found", username=login_request.username, ip=client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    user_id, username, password_hash, is_active = row

    if not is_active:
        throttle.record_failure(client_ip)
        logger.warning("login_failed_user_inactive", username=username, ip=client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    # Verify password
    if not verify_password(login_request.password, password_hash):
        throttle.record_failure(client_ip)
        logger.warning("login_failed_invalid_password", username=username, ip=client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Successful login - clear throttle and update last_login_at
    throttle.clear(client_ip)

    await repo._connection.execute(
        "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), user_id),
    )
    await repo._connection.commit()

    # Create tokens
    token_data = {"sub": username, "user_id": user_id}

    access_token = create_access_token(
        data=token_data,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_expires_minutes,
    )

    refresh_token = create_refresh_token(
        data=token_data,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.refresh_token_expires_minutes,
    )

    logger.info("login_successful", username=username, user_id=user_id, ip=client_ip)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_expires_minutes * 60,  # Convert to seconds
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    responses={
        200: {"description": "New tokens issued"},
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(
    refresh_request: RefreshRequest,
    repo: VideoRepository = Depends(get_repository),
    settings: APISettings = Depends(get_api_settings),
) -> TokenResponse:
    """
    Refresh an access token using a valid refresh token.

    Returns new access and refresh tokens.
    """
    # Decode refresh token
    payload = decode_token(
        token=refresh_request.refresh_token,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expected_type="refresh",
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    username = payload.get("sub")

    if not user_id or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Verify user still exists and is active
    cursor = await repo._connection.execute(
        "SELECT id, username, is_active FROM users WHERE id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()

    if not row or not row[2]:  # not found or not active
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )

    # Create new tokens
    token_data = {"sub": username, "user_id": user_id}

    new_access_token = create_access_token(
        data=token_data,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_expires_minutes,
    )

    new_refresh_token = create_refresh_token(
        data=token_data,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.refresh_token_expires_minutes,
    )

    logger.info("token_refreshed", username=username, user_id=user_id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_expires_minutes * 60,
    )


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password",
    responses={
        204: {"description": "Password changed successfully"},
        400: {"description": "Invalid current password or new password requirements not met"},
        401: {"description": "Authentication required"},
    },
)
async def change_password(
    password_request: PasswordChangeRequest,
    user: UserInfo = Depends(require_auth),
    repo: VideoRepository = Depends(get_repository),
    settings: APISettings = Depends(get_api_settings),
) -> None:
    """
    Change the password for the authenticated user.

    Requires authentication. Validates current password before updating.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Get current password hash
    cursor = await repo._connection.execute(
        "SELECT password_hash FROM users WHERE id = ?",
        (user.id,),
    )
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    current_hash = row[0]

    # Verify current password
    if not verify_password(password_request.current_password, current_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Hash and store new password
    new_hash = hash_password(password_request.new_password)

    await repo._connection.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
        (new_hash, datetime.now(timezone.utc).isoformat(), user.id),
    )
    await repo._connection.commit()

    logger.info("password_changed", user_id=user.id, username=user.username)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout (no-op for stateless JWT)",
    responses={
        204: {"description": "Logout acknowledged"},
    },
)
async def logout() -> None:
    """
    Logout endpoint (no-op for stateless JWT).

    Since JWT tokens are stateless, this endpoint doesn't invalidate tokens.
    Clients should discard tokens on logout.

    Note: For true token invalidation, implement a token blacklist
    (requires Redis or database storage - out of scope for single-user auth).
    """
    # No-op: stateless JWT means no server-side session to invalidate
    # Client should discard tokens
    pass
