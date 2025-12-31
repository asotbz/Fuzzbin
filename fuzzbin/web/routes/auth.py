"""Authentication routes for login, logout, password change, and token refresh."""

from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from fuzzbin.auth import (
    LoginRequest,
    TokenResponse,
    AccessTokenResponse,
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
    revoke_token,
    revoke_all_user_tokens,
    set_refresh_cookie,
    clear_refresh_cookie,
)
from fuzzbin.core.db import VideoRepository

from ..dependencies import get_repository, get_api_settings, require_auth
from ..settings import APISettings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Bearer token security scheme for logout
bearer_scheme = HTTPBearer(auto_error=False)


class SetInitialPasswordRequest(BaseModel):
    """Request body for setting initial password."""

    username: str = Field(..., min_length=1, description="Username")
    current_password: str = Field(
        ..., min_length=1, description="Current password (default: changeme)"
    )
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class PasswordRotationRequiredResponse(BaseModel):
    """Response when password rotation is required."""

    detail: str = "Password change required"
    redirect_to: str = "/auth/set-initial-password"
    message: str = "Your account requires a password change before you can log in."


def get_client_ip(request: Request, settings: APISettings = None) -> str:
    """Extract client IP from request, considering trusted proxies.

    Only parses X-Forwarded-For when trusted_proxy_count > 0.
    Takes the Nth-from-right IP where N = trusted_proxy_count.
    """
    if settings and settings.trusted_proxy_count > 0:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ips = [ip.strip() for ip in forwarded.split(",")]
            # Take Nth from right (trusted_proxy_count determines how many proxies we trust)
            index = max(0, len(ips) - settings.trusted_proxy_count)
            return ips[index]
    return request.client.host if request.client else "unknown"


@router.post(
    "/login",
    response_model=AccessTokenResponse,
    summary="Authenticate user",
    responses={
        200: {"description": "Successful authentication (refresh token set as httpOnly cookie)"},
        401: {"description": "Invalid credentials"},
        403: {"description": "Password change required", "model": PasswordRotationRequiredResponse},
        429: {"description": "Too many failed attempts"},
    },
)
async def login(
    request: Request,
    response: Response,
    login_request: LoginRequest,
    repo: VideoRepository = Depends(get_repository),
    settings: APISettings = Depends(get_api_settings),
    throttle: LoginThrottle = Depends(get_login_throttle),
) -> AccessTokenResponse:
    """
    Authenticate a user and return JWT access token.

    Validates username and password, returns access token in response body
    and sets refresh token as an httpOnly cookie for security.

    If the user's password_must_change flag is set, returns 403 with
    instructions to use /auth/set-initial-password endpoint.

    Rate limited: 5 failed attempts per minute per IP address.
    """
    client_ip = get_client_ip(request, settings)

    # Check if IP is throttled
    if throttle.is_blocked(client_ip):
        retry_after = throttle.get_retry_after(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # Look up user (including password_must_change flag)
    cursor = await repo._connection.execute(
        "SELECT id, username, password_hash, is_active, password_must_change FROM users WHERE username = ?",
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

    user_id, username, password_hash, is_active, password_must_change = row

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

    # Check if password rotation is required
    if password_must_change:
        logger.info("login_blocked_password_rotation_required", username=username, user_id=user_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required. Use /auth/set-initial-password to set a new password.",
            headers={"X-Password-Change-Required": "true"},
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

    # Set refresh token as httpOnly cookie
    set_refresh_cookie(response, refresh_token, settings)

    return AccessTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expires_minutes * 60,  # Convert to seconds
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Refresh access token",
    responses={
        200: {"description": "New access token issued (refresh token rotated via httpOnly cookie)"},
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh_token(
    response: Response,
    refresh_token_cookie: Optional[str] = Cookie(None, alias="refresh_token"),
    repo: VideoRepository = Depends(get_repository),
    settings: APISettings = Depends(get_api_settings),
) -> AccessTokenResponse:
    """
    Refresh an access token using a valid refresh token.

    The refresh token is read from the httpOnly cookie set during login.
    Returns new access token in response body and rotates the refresh
    token cookie.
    """
    # Check if refresh token cookie exists
    if not refresh_token_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Decode refresh token from cookie
    payload = decode_token(
        token=refresh_token_cookie,
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

    # Rotate refresh token cookie
    set_refresh_cookie(response, new_refresh_token, settings)

    return AccessTokenResponse(
        access_token=new_access_token,
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
    Note: Password change does not guarantee immediate server-side revocation of
    previously issued JWTs. Clients should discard existing tokens and re-authenticate.

    Remediation note: implement true "revoke all tokens" with a DB-backed mechanism
    (e.g., per-user token versioning) so old tokens are reliably rejected.
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

    # Invalidate all existing tokens for this user
    await revoke_all_user_tokens(
        user_id=user.id,
        reason="password_changed",
        connection=repo._connection,
    )

    logger.info("password_changed", user_id=user.id, username=user.username)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and revoke tokens",
    responses={
        204: {"description": "Tokens revoked successfully"},
        401: {"description": "Invalid or missing token"},
    },
)
async def logout(
    response: Response,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    settings: APISettings = Depends(get_api_settings),
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """
    Logout and revoke the current access token.

    The provided Bearer token will be added to the revocation list,
    preventing it from being used again even if it hasn't expired.

    Also clears the httpOnly refresh token cookie.
    """
    # Always clear the refresh token cookie
    clear_refresh_cookie(response, settings)

    if not credentials:
        # No token provided - nothing else to revoke
        return

    token = credentials.credentials
    payload = decode_token(
        token=token,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        check_revoked=False,  # Don't fail if already revoked
    )

    if not payload:
        # Invalid token - nothing to revoke
        return

    jti = payload.get("jti")
    user_id = payload.get("user_id")
    exp = payload.get("exp")

    if jti and user_id and exp:
        # Convert exp timestamp to datetime
        expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)

        await revoke_token(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            reason="logout",
            connection=repo._connection,
        )

        logger.info("logout_token_revoked", user_id=user_id, jti=jti)


@router.post(
    "/set-initial-password",
    response_model=AccessTokenResponse,
    summary="Set initial password for first-time setup",
    responses={
        200: {
            "description": "Password changed, access token issued (refresh token set as httpOnly cookie)"
        },
        400: {"description": "Invalid current password or new password requirements not met"},
        401: {"description": "Invalid credentials"},
        403: {"description": "Password rotation not required for this user"},
        429: {"description": "Too many failed attempts"},
    },
)
async def set_initial_password(
    request: Request,
    response: Response,
    password_request: SetInitialPasswordRequest,
    repo: VideoRepository = Depends(get_repository),
    settings: APISettings = Depends(get_api_settings),
    throttle: LoginThrottle = Depends(get_login_throttle),
) -> TokenResponse:
    """
    Set a new password for users requiring password rotation.

    This endpoint is used during first-time setup or when an admin has
    reset a user's password. It validates the current password, sets
    the new password, clears the password_must_change flag, and returns
    authentication tokens.

    Unlike /auth/password, this endpoint does not require prior authentication
    and is specifically for users who cannot log in due to password rotation
    requirements.
    """
    client_ip = get_client_ip(request, settings)

    # Check if IP is throttled
    if throttle.is_blocked(client_ip):
        retry_after = throttle.get_retry_after(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    # Look up user
    cursor = await repo._connection.execute(
        "SELECT id, username, password_hash, is_active, password_must_change FROM users WHERE username = ?",
        (password_request.username,),
    )
    row = await cursor.fetchone()

    if not row:
        throttle.record_failure(client_ip)
        logger.warning(
            "set_initial_password_user_not_found", username=password_request.username, ip=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    user_id, username, password_hash, is_active, password_must_change = row

    if not is_active:
        throttle.record_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    # Verify this user actually requires password rotation
    if not password_must_change:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password rotation is not required for this user. Use /auth/password instead.",
        )

    # Verify current password
    if not verify_password(password_request.current_password, password_hash):
        throttle.record_failure(client_ip)
        logger.warning("set_initial_password_invalid_current", username=username, ip=client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Ensure new password is different from current
    if password_request.new_password == password_request.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    # Hash and store new password, clear the rotation flag
    new_hash = hash_password(password_request.new_password)
    now = datetime.now(timezone.utc).isoformat()

    await repo._connection.execute(
        "UPDATE users SET password_hash = ?, password_must_change = 0, last_login_at = ?, updated_at = ? WHERE id = ?",
        (new_hash, now, now, user_id),
    )
    await repo._connection.commit()

    # Clear throttle on success
    throttle.clear(client_ip)

    # Create tokens for immediate login
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

    logger.info("initial_password_set", username=username, user_id=user_id, ip=client_ip)

    # Set refresh token as httpOnly cookie
    set_refresh_cookie(response, refresh_token, settings)

    return AccessTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expires_minutes * 60,
    )
