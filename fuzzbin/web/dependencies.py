"""FastAPI dependency injection for database, authentication, and services."""

from typing import AsyncGenerator, Optional

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import fuzzbin
from fuzzbin.auth import check_token_revoked_in_db, decode_token, UserInfo
from fuzzbin.core.db import VideoRepository
from fuzzbin.services import ImportService, SearchService, VideoService
from fuzzbin.services.base import ServiceCallback

from .settings import APISettings, get_settings

logger = structlog.get_logger(__name__)

# Optional bearer scheme - doesn't require auth header, allows checking if present
optional_bearer = HTTPBearer(auto_error=False)


async def get_repository() -> AsyncGenerator[VideoRepository, None]:
    """
    Dependency that provides a VideoRepository instance.

    Yields the repository from the configured fuzzbin module.
    Requires fuzzbin.configure() to have been called (done in app lifespan).

    Yields:
        VideoRepository instance

    Example:
        @router.get("/videos")
        async def list_videos(repo: VideoRepository = Depends(get_repository)):
            ...
    """
    repo = await fuzzbin.get_repository()
    yield repo


def get_api_settings() -> APISettings:
    """
    Dependency that provides API settings.

    Returns:
        APISettings instance (cached)
    """
    return get_settings()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
    settings: APISettings = Depends(get_api_settings),
    repo: VideoRepository = Depends(get_repository),
) -> Optional[UserInfo]:
    """
    Dependency that extracts and validates the current user from JWT token.

    When auth_enabled=False, returns None (allowing unauthenticated access).
    When auth_enabled=True, validates the Bearer token and returns user info.

    Args:
        credentials: HTTP Bearer authorization credentials (optional)
        settings: API settings containing JWT configuration
        repo: Database repository for user lookup

    Returns:
        UserInfo if authenticated, None if auth disabled or no token provided

    Raises:
        HTTPException(401): If auth enabled and token is invalid/expired
    """
    # Auth disabled - return None (unauthenticated access allowed)
    if not settings.auth_enabled:
        return None

    # No credentials provided
    if not credentials:
        return None

    # Decode and validate token
    token = credentials.credentials
    payload = decode_token(
        token=token,
        secret_key=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expected_type="access",
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user info from token
    user_id = payload.get("user_id")
    username = payload.get("sub")
    jti = payload.get("jti")

    if not user_id or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Enforce DB-backed denylist checks (cache-first with DB fallback)
    if jti:
        is_revoked = await check_token_revoked_in_db(jti=jti, connection=repo._connection)
        if is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Verify user exists and is active in database
    cursor = await repo._connection.execute(
        "SELECT id, username, is_active, last_login_at FROM users WHERE id = ?",
        (user_id,),
    )
    row = await cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not row[2]:  # is_active
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return UserInfo(
        id=row[0],
        username=row[1],
        is_active=bool(row[2]),
        last_login_at=row[3],
    )


async def require_auth(
    user: Optional[UserInfo] = Depends(get_current_user),
    settings: APISettings = Depends(get_api_settings),
) -> Optional[UserInfo]:
    """
    Dependency that requires authentication when auth is enabled.

    Use this as a route dependency to protect endpoints.
    When auth_enabled=False, allows access without authentication.
    When auth_enabled=True, requires a valid JWT token.

    Args:
        user: Current user from get_current_user
        settings: API settings

    Returns:
        UserInfo if authenticated, None if auth disabled

    Raises:
        HTTPException(401): If auth enabled and no valid token provided

    Example:
        @router.get("/protected")
        async def protected_route(user: UserInfo = Depends(require_auth)):
            return {"message": f"Hello, {user.username}"}
    """
    # Auth disabled - allow access
    if not settings.auth_enabled:
        return None

    # Auth enabled but no user - reject
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug("request_authenticated", user_id=user.id, username=user.username)
    return user


# ==================== Service Dependencies ====================


async def get_video_service(
    repo: VideoRepository = Depends(get_repository),
) -> VideoService:
    """
    Dependency that provides a VideoService instance.

    The service is created per-request with the repository dependency.

    Args:
        repo: VideoRepository from get_repository dependency

    Returns:
        VideoService instance

    Example:
        @router.get("/videos/{video_id}")
        async def get_video(
            video_id: int,
            video_service: VideoService = Depends(get_video_service)
        ):
            return await video_service.get_with_relationships(video_id)
    """
    return VideoService(repository=repo)


async def get_import_service(
    repo: VideoRepository = Depends(get_repository),
) -> ImportService:
    """
    Dependency that provides an ImportService instance.

    The service is created per-request with the repository dependency.
    For Spotify imports, you'll need to pass a SpotifyClient explicitly.

    Args:
        repo: VideoRepository from get_repository dependency

    Returns:
        ImportService instance

    Example:
        @router.post("/imports/nfo")
        async def import_nfo(
            directory: str,
            import_service: ImportService = Depends(get_import_service)
        ):
            return await import_service.import_nfo_directory(Path(directory))
    """
    return ImportService(repository=repo)


async def get_search_service(
    repo: VideoRepository = Depends(get_repository),
) -> SearchService:
    """
    Dependency that provides a SearchService instance.

    The service is created per-request with the repository dependency.
    Note: Cached methods maintain their cache across requests.

    Args:
        repo: VideoRepository from get_repository dependency

    Returns:
        SearchService instance

    Example:
        @router.get("/search")
        async def search(
            q: str,
            search_service: SearchService = Depends(get_search_service)
        ):
            return await search_service.search_videos(q)
    """
    return SearchService(repository=repo)
