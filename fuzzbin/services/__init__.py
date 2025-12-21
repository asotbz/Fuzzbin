"""Service layer for orchestrating business logic.

This module provides service classes that consolidate scattered business logic
from API routes, workflows, and task handlers into cohesive, testable services.
Services orchestrate repositories, file operations, and external APIs while
enforcing business rules.

Example:
    >>> from fuzzbin.services import VideoService, ImportService
    >>> 
    >>> # Use via FastAPI dependency injection
    >>> async def my_route(video_service: VideoService = Depends(get_video_service)):
    ...     video = await video_service.get_with_relationships(video_id)
"""

from .base import (
    BaseService,
    ServiceCallback,
    ServiceError,
    ValidationError,
    NotFoundError,
    ConflictError,
    cached_async,
)
from .video_service import VideoService
from .import_service import ImportService
from .search_service import SearchService

__all__ = [
    # Base classes and utilities
    "BaseService",
    "ServiceCallback",
    "ServiceError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "cached_async",
    # Services
    "VideoService",
    "ImportService",
    "SearchService",
]
