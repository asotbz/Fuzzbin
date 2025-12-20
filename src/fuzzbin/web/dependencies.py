"""FastAPI dependency injection for database and authentication."""

from typing import AsyncGenerator, Optional

import fuzzbin
from fuzzbin.core.db import VideoRepository

from .settings import APISettings, get_settings


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


async def get_current_user() -> Optional[dict]:
    """
    Dependency stub for current authenticated user.

    Phase 1: Returns None (no authentication)
    Phase 2: Will return authenticated user dict with id, username, roles

    Returns:
        None (Phase 1 - auth-less)
        dict with user info (Phase 2+)
    """
    # Phase 2: Implement JWT token validation
    # token = request.headers.get("Authorization")
    # if token:
    #     return decode_and_validate_token(token)
    return None
