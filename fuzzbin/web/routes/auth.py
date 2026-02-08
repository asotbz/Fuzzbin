"""Authentication routes for login, logout, password change, and token refresh."""

from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from fuzzbin.auth import (
    LoginRequest,
    TokenResponse,
    AccessTokenResponse,
    PasswordChangeRequest,
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
from fuzzbin.auth.oidc import (
    OIDCError,
    OIDCConfigError,
    OIDCValidationError,
    OIDCProvider,
    get_oidc_provider,
    get_oidc_transaction_store,
)
from fuzzbin.core.db import VideoRepository

import fuzzbin as fuzzbin_app

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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _issue_tokens(
    user_id: int,
    username: str,
    settings: APISettings,
    response: Response,
    repo: VideoRepository,
) -> AccessTokenResponse:
    """Create access + refresh tokens, set the refresh cookie, and update last_login_at.

    This is the single code-path used by both password login and OIDC login.
    """
    now = datetime.now(timezone.utc).isoformat()
    await repo._connection.execute(
        "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
        (now, now, user_id),
    )
    await repo._connection.commit()

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

    set_refresh_cookie(response, refresh_token, settings)

    return AccessTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expires_minutes * 60,
    )


def _oidc_debug_context(oidc_cfg: Any) -> dict[str, Any]:
    """Build sanitized OIDC diagnostics for logs and errors."""
    return {
        "enabled": bool(getattr(oidc_cfg, "enabled", False)),
        "issuer_url": getattr(oidc_cfg, "issuer_url", None),
        "client_id": getattr(oidc_cfg, "client_id", None),
        "redirect_uri": getattr(oidc_cfg, "redirect_uri", None),
        "target_username": getattr(oidc_cfg, "target_username", None),
        "scopes": getattr(oidc_cfg, "scopes", None),
        "client_secret_set": bool(getattr(oidc_cfg, "client_secret", None)),
    }


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

    if repo._connection is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not initialized",
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

    # Successful login - clear throttle and issue tokens
    throttle.clear(client_ip)

    logger.info("login_successful", username=username, user_id=user_id, ip=client_ip)

    return await _issue_tokens(user_id, username, settings, response, repo)


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

    logger.info("initial_password_set", username=username, user_id=user_id, ip=client_ip)

    return await _issue_tokens(user_id, username, settings, response, repo)


# ---------------------------------------------------------------------------
# OIDC schemas
# ---------------------------------------------------------------------------


class OIDCConfigResponse(BaseModel):
    """Public OIDC configuration for the frontend."""

    enabled: bool = Field(..., description="Whether OIDC login is available")
    provider_name: str = Field(default="SSO", description="Display label for the login button")


class OIDCLogoutURLResponse(BaseModel):
    """Response from /auth/oidc/logout-url."""

    logout_url: Optional[str] = Field(
        default=None,
        description="OIDC end-session URL, or null when provider logout is unavailable",
    )


class OIDCStartRequest(BaseModel):
    """(Empty body — may carry optional fields in future.)"""


class OIDCStartResponse(BaseModel):
    """Response from /auth/oidc/start with the authorization URL."""

    auth_url: str = Field(..., description="URL to redirect the user to for IdP login")
    state: str = Field(..., description="Opaque state value for CSRF verification")


class OIDCExchangeRequest(BaseModel):
    """Request body for /auth/oidc/exchange."""

    code: str = Field(..., min_length=1, description="Authorization code from the IdP callback")
    state: str = Field(..., min_length=1, description="State value from the original auth request")


# ---------------------------------------------------------------------------
# OIDC endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/oidc/config",
    response_model=OIDCConfigResponse,
    summary="Get OIDC configuration",
    responses={200: {"description": "OIDC availability and display label"}},
)
async def oidc_config() -> OIDCConfigResponse:
    """Return whether OIDC login is enabled and provider display name.

    This is a public endpoint — the frontend calls it on load to decide
    whether to show the OIDC login button.
    """
    oidc_cfg = fuzzbin_app.get_config().oidc
    return OIDCConfigResponse(
        enabled=oidc_cfg.enabled,
        provider_name=oidc_cfg.provider_name if oidc_cfg.enabled else "SSO",
    )


@router.get(
    "/oidc/logout-url",
    response_model=OIDCLogoutURLResponse,
    summary="Get OIDC logout URL",
    responses={
        200: {
            "description": "OIDC logout URL (or null if provider does not support RP-initiated logout)"
        },
        404: {"description": "OIDC is not enabled"},
        500: {"description": "OIDC discovery or configuration error"},
    },
)
async def oidc_logout_url(
    post_logout_redirect_uri: Optional[str] = Query(
        default=None,
        description="Optional URL for IdP post-logout redirect",
    ),
) -> OIDCLogoutURLResponse:
    """Return the IdP end-session URL for browser redirect after local logout."""
    oidc_cfg = fuzzbin_app.get_config().oidc
    if not oidc_cfg.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC is not enabled")

    try:
        provider = get_oidc_provider(oidc_cfg)
        logout_url = await provider.build_logout_url(
            post_logout_redirect_uri=post_logout_redirect_uri,
        )
        return OIDCLogoutURLResponse(logout_url=logout_url)
    except OIDCConfigError as exc:
        logger.error(
            "oidc_logout_url_config_error",
            error=str(exc),
            oidc=_oidc_debug_context(oidc_cfg),
            hint="Check config.oidc required fields and restart.",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OIDC configuration error: {exc}",
        ) from exc
    except Exception as exc:
        logger.error(
            "oidc_logout_url_unexpected_error",
            error=str(exc),
            oidc=_oidc_debug_context(oidc_cfg),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build OIDC logout URL. Check server logs for details.",
        ) from exc


@router.post(
    "/oidc/start",
    response_model=OIDCStartResponse,
    summary="Start OIDC login flow",
    responses={
        200: {"description": "Authorization URL and state"},
        404: {"description": "OIDC is not enabled"},
        500: {"description": "OIDC discovery or configuration error"},
    },
)
async def oidc_start() -> OIDCStartResponse:
    """Create OIDC authorization request (state, nonce, PKCE) and return the auth URL.

    The frontend should redirect the user to ``auth_url``. After IdP
    authentication the user is redirected back to ``oidc_redirect_uri``
    with ``code`` and ``state`` query params.
    """
    oidc_cfg = fuzzbin_app.get_config().oidc
    if not oidc_cfg.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC is not enabled")

    try:
        provider = get_oidc_provider(oidc_cfg)
        store = get_oidc_transaction_store()

        state, nonce, code_verifier = store.create()
        auth_url = await provider.build_auth_url(state, nonce, code_verifier)

        logger.info("oidc_auth_started", state=state[:8] + "…")
        return OIDCStartResponse(auth_url=auth_url, state=state)
    except OIDCConfigError as exc:
        logger.error(
            "oidc_start_config_error",
            error=str(exc),
            oidc=_oidc_debug_context(oidc_cfg),
            hint="Check config.oidc required fields and restart.",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OIDC configuration error: {exc}",
        ) from exc
    except Exception as exc:
        logger.error(
            "oidc_start_unexpected_error",
            error=str(exc),
            oidc=_oidc_debug_context(oidc_cfg),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start OIDC login. Check server logs for details.",
        ) from exc


@router.post(
    "/oidc/exchange",
    response_model=AccessTokenResponse,
    summary="Exchange OIDC authorization code for local tokens",
    responses={
        200: {"description": "Local JWT issued (refresh token set as httpOnly cookie)"},
        400: {"description": "Invalid state, expired transaction, or token exchange error"},
        403: {"description": "Identity binding mismatch or missing required group"},
        404: {"description": "OIDC is not enabled"},
        500: {"description": "OIDC configuration or server-side lookup error"},
    },
)
async def oidc_exchange(
    response: Response,
    exchange_request: OIDCExchangeRequest,
    repo: VideoRepository = Depends(get_repository),
    settings: APISettings = Depends(get_api_settings),
) -> AccessTokenResponse:
    """Validate the OIDC callback, exchange the code, validate the ID token,
    enforce identity binding, and issue local JWT tokens.

    The frontend calls this after the IdP redirects back with ``code`` and
    ``state``.  On success the response is identical to ``POST /auth/login``:
    access token in the body, refresh token as httpOnly cookie.
    """
    oidc_cfg = fuzzbin_app.get_config().oidc
    if not oidc_cfg.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OIDC is not enabled")

    # --- 1. Consume the transaction (state → nonce + code_verifier) ----------
    store = get_oidc_transaction_store()
    consumed = store.consume(exchange_request.state)
    if consumed is None:
        logger.warning("oidc_exchange_invalid_state", state=exchange_request.state[:8] + "…")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OIDC state. Please restart the login flow.",
        )

    nonce, code_verifier = consumed

    try:
        provider = get_oidc_provider(oidc_cfg)

        # --- 2. Exchange authorization code -----------------------------------
        token_response = await provider.exchange_code(exchange_request.code, code_verifier)
        id_token_str = token_response.get("id_token")
        if not id_token_str:
            raise OIDCError("Token response missing id_token")

        # --- 3. Validate ID token ---------------------------------------------
        claims = await provider.validate_id_token(id_token_str, nonce)

        # --- 4. Optional group gating -----------------------------------------
        OIDCProvider.check_group_claim(
            claims,
            required_group=oidc_cfg.required_group,
            groups_claim=oidc_cfg.groups_claim,
        )

        # --- 5. Optional allowed_subject check --------------------------------
        if oidc_cfg.allowed_subject and claims["sub"] != oidc_cfg.allowed_subject:
            logger.warning(
                "oidc_exchange_subject_denied",
                sub=claims["sub"],
                allowed=oidc_cfg.allowed_subject,
            )
            raise OIDCValidationError("Your identity is not authorized to log in to this instance.")

    except OIDCValidationError as exc:
        logger.warning("oidc_exchange_validation_failed", error=str(exc))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except OIDCConfigError as exc:
        logger.error(
            "oidc_exchange_config_error",
            error=str(exc),
            oidc=_oidc_debug_context(oidc_cfg),
            hint="Check config.oidc required fields and restart.",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OIDC configuration error: {exc}",
        ) from exc
    except OIDCError as exc:
        logger.warning("oidc_exchange_error", error=str(exc))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # --- 6. Resolve target local user -----------------------------------------
    oidc_iss = claims["iss"]
    oidc_sub = claims["sub"]

    if repo._connection is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not initialized",
        )

    try:
        cursor = await repo._connection.execute(
            "SELECT id, username, is_active, oidc_issuer, oidc_subject FROM users WHERE username = ?",
            (oidc_cfg.target_username,),
        )
        row = await cursor.fetchone()
    except Exception as exc:
        logger.error(
            "oidc_exchange_user_lookup_failed",
            error=str(exc),
            oidc=_oidc_debug_context(oidc_cfg),
            hint=(
                "Ensure migration 004_oidc_identity.sql is applied and oidc.target_username exists."
            ),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "OIDC user binding lookup failed. Ensure migration "
                "004_oidc_identity.sql is applied and target user exists."
            ),
        ) from exc

    if not row:
        logger.warning("oidc_exchange_target_user_missing", target=oidc_cfg.target_username)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Target local user does not exist.",
        )

    user_id, username, is_active, existing_iss, existing_sub = row

    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Target local user account is disabled.",
        )

    # --- 7. Identity binding --------------------------------------------------
    if existing_iss is None and existing_sub is None:
        # First-time bind
        await repo._connection.execute(
            "UPDATE users SET oidc_issuer = ?, oidc_subject = ?, updated_at = ? WHERE id = ?",
            (oidc_iss, oidc_sub, datetime.now(timezone.utc).isoformat(), user_id),
        )
        await repo._connection.commit()
        logger.info(
            "oidc_identity_bound",
            user_id=user_id,
            username=username,
            iss=oidc_iss,
            sub=oidc_sub,
        )
    else:
        # Verify existing binding
        if existing_iss != oidc_iss or existing_sub != oidc_sub:
            logger.warning(
                "oidc_exchange_identity_mismatch",
                user_id=user_id,
                expected_iss=existing_iss,
                expected_sub=existing_sub,
                actual_iss=oidc_iss,
                actual_sub=oidc_sub,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="OIDC identity does not match the bound identity for this user.",
            )

    # --- 8. Issue local tokens ------------------------------------------------
    logger.info(
        "oidc_login_successful", user_id=user_id, username=username, iss=oidc_iss, sub=oidc_sub
    )
    return await _issue_tokens(user_id, username, settings, response, repo)
