"""FastAPI dependency injection for database, authentication, and services."""

from typing import AsyncGenerator, Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import fuzzbin
from fuzzbin.api.discogs_client import DiscogsClient
from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.api.musicbrainz_client import MusicBrainzClient
from fuzzbin.api.spotify_client import SpotifyClient
from fuzzbin.auth import check_token_revoked_in_db, decode_token, UserInfo
from fuzzbin.core.db import VideoRepository
from fuzzbin.services import ImportService, SearchService, TagService, VideoService

from .settings import APISettings, get_settings

logger = structlog.get_logger(__name__)

# ==================== Shared API Client Singletons ====================
# These clients are initialized once and shared across all requests for
# proper rate limiting, connection pooling, and cache sharing.

_imvdb_client: Optional[IMVDbClient] = None
_discogs_client: Optional[DiscogsClient] = None
_spotify_client: Optional[SpotifyClient] = None
_musicbrainz_client: Optional[MusicBrainzClient] = None

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

    if repo._connection is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection not initialized",
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


async def get_tag_service(
    repo: VideoRepository = Depends(get_repository),
) -> TagService:
    """
    Dependency that provides a TagService instance.

    The service is created per-request with the repository dependency.
    Tag mutations through this service automatically sync NFO files.

    Args:
        repo: VideoRepository from get_repository dependency

    Returns:
        TagService instance
    """
    return TagService(repository=repo)


# ==================== External API Client Dependencies ====================


async def get_imvdb_client() -> AsyncGenerator[IMVDbClient, None]:
    """
    Dependency that provides a shared IMVDb client instance.

    The client is initialized once on first request and reused across all
    subsequent requests. This ensures proper rate limiting, connection pooling,
    and cache sharing across the application.

    The client is cleaned up during application shutdown via the lifespan handler.

    Yields:
        IMVDbClient instance

    Raises:
        HTTPException(503): If IMVDb API is not configured

    Example:
        @router.get("/imvdb/videos/{video_id}")
        async def get_video(
            video_id: int,
            client: IMVDbClient = Depends(get_imvdb_client)
        ):
            return await client.get_video(video_id)
    """
    global _imvdb_client

    if _imvdb_client is None:
        config = fuzzbin.get_config()
        if config.apis is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API configuration not available",
            )
        api_config = config.apis.get("imvdb")

        if not api_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="IMVDb API is not configured",
            )

        _imvdb_client = IMVDbClient.from_config(api_config)
        await _imvdb_client.__aenter__()
        logger.info("imvdb_client_initialized_singleton")

    yield _imvdb_client


async def get_discogs_client() -> AsyncGenerator[DiscogsClient, None]:
    """
    Dependency that provides a shared Discogs client instance.

    The client is initialized once on first request and reused across all
    subsequent requests. This ensures proper rate limiting, connection pooling,
    and cache sharing across the application.

    The client is cleaned up during application shutdown via the lifespan handler.

    Yields:
        DiscogsClient instance

    Raises:
        HTTPException(503): If Discogs API is not configured

    Example:
        @router.get("/discogs/masters/{master_id}")
        async def get_master(
            master_id: int,
            client: DiscogsClient = Depends(get_discogs_client)
        ):
            return await client.get_master(master_id)
    """
    global _discogs_client

    if _discogs_client is None:
        config = fuzzbin.get_config()
        if config.apis is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API configuration not available",
            )
        api_config = config.apis.get("discogs")

        if not api_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Discogs API is not configured",
            )

        _discogs_client = DiscogsClient.from_config(api_config)
        await _discogs_client.__aenter__()
        logger.info("discogs_client_initialized_singleton")

    yield _discogs_client


async def get_spotify_client() -> AsyncGenerator[SpotifyClient, None]:
    """
    Dependency that provides a shared Spotify client instance.

    The client is initialized once on first request and reused across all
    subsequent requests. This ensures proper rate limiting, connection pooling,
    and cache sharing across the application.

    The client handles OAuth token management automatically using the
    SpotifyTokenManager for Client Credentials flow.

    The client is cleaned up during application shutdown via the lifespan handler.

    Yields:
        SpotifyClient instance

    Raises:
        HTTPException(503): If Spotify API is not configured

    Example:
        @router.get("/spotify/playlists/{playlist_id}")
        async def get_playlist(
            playlist_id: str,
            client: SpotifyClient = Depends(get_spotify_client)
        ):
            return await client.get_playlist(playlist_id)
    """
    global _spotify_client

    if _spotify_client is None:
        config = fuzzbin.get_config()
        if config.apis is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API configuration not available",
            )
        api_config = config.apis.get("spotify")

        if not api_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Spotify API is not configured",
            )

        _spotify_client = SpotifyClient.from_config(api_config)
        await _spotify_client.__aenter__()
        logger.info("spotify_client_initialized_singleton")

    yield _spotify_client


async def get_musicbrainz_client() -> AsyncGenerator[MusicBrainzClient, None]:
    """
    Dependency that provides a shared MusicBrainz client instance.

    The client is initialized once on first request and reused across all
    subsequent requests. This ensures proper rate limiting, connection pooling,
    and cache sharing across the application.

    The client is cleaned up during application shutdown via the lifespan handler.

    Yields:
        MusicBrainzClient instance

    Raises:
        HTTPException(503): If MusicBrainz API is not configured

    Example:
        @router.get("/musicbrainz/recordings/{mbid}")
        async def get_recording(
            mbid: str,
            client: MusicBrainzClient = Depends(get_musicbrainz_client)
        ):
            return await client.get_recording(mbid)
    """
    global _musicbrainz_client

    if _musicbrainz_client is None:
        config = fuzzbin.get_config()
        if config.apis is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API configuration not available",
            )
        api_config = config.apis.get("musicbrainz")

        if not api_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MusicBrainz API is not configured",
            )

        _musicbrainz_client = MusicBrainzClient.from_config(api_config)
        await _musicbrainz_client.__aenter__()
        logger.info("musicbrainz_client_initialized_singleton")

    yield _musicbrainz_client


async def cleanup_api_clients() -> None:
    """
    Clean up shared API client instances.

    Called during application shutdown to properly close HTTP connections
    and release resources.
    """
    global _imvdb_client, _discogs_client, _spotify_client, _musicbrainz_client

    if _imvdb_client is not None:
        await _imvdb_client.__aexit__(None, None, None)
        _imvdb_client = None
        logger.info("imvdb_client_cleanup_complete")

    if _discogs_client is not None:
        await _discogs_client.__aexit__(None, None, None)
        _discogs_client = None
        logger.info("discogs_client_cleanup_complete")

    if _spotify_client is not None:
        await _spotify_client.__aexit__(None, None, None)
        _spotify_client = None
        logger.info("spotify_client_cleanup_complete")

    if _musicbrainz_client is not None:
        await _musicbrainz_client.__aexit__(None, None, None)
        _musicbrainz_client = None
        logger.info("musicbrainz_client_cleanup_complete")
