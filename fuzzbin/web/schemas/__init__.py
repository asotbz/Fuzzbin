"""Pydantic schemas for API request/response DTOs."""

from .common import (
    AUTH_ERROR_RESPONSES,
    COMMON_ERROR_RESPONSES,
    PUBLIC_ERROR_RESPONSES,
    ErrorDetail,
    HealthCheckResponse,
    PageParams,
    PaginatedResponse,
    SearchSuggestionsResponse,
    SortParams,
    ValidationErrorDetail,
    ValidationErrorResponse,
    VideoStatusHistoryEntry,
    VideoStatusHistoryResponse,
)
from .video import (
    VideoCreate,
    VideoFilters,
    VideoResponse,
    VideoUpdate,
    VideoStatusUpdate,
)
from .artist import ArtistCreate, ArtistResponse, ArtistUpdate, ArtistVideoLink
from .collection import (
    CollectionCreate,
    CollectionResponse,
    CollectionUpdate,
    CollectionVideoAdd,
)
from .tag import TagCreate, TagResponse, TagsSet

__all__ = [
    # Common
    "PageParams",
    "SortParams",
    "PaginatedResponse",
    # Error responses
    "ErrorDetail",
    "ValidationErrorDetail",
    "ValidationErrorResponse",
    "COMMON_ERROR_RESPONSES",
    "PUBLIC_ERROR_RESPONSES",
    "AUTH_ERROR_RESPONSES",
    # Concrete response models
    "HealthCheckResponse",
    "SearchSuggestionsResponse",
    "VideoStatusHistoryEntry",
    "VideoStatusHistoryResponse",
    # Video
    "VideoCreate",
    "VideoUpdate",
    "VideoResponse",
    "VideoFilters",
    "VideoStatusUpdate",
    # Artist
    "ArtistCreate",
    "ArtistUpdate",
    "ArtistResponse",
    "ArtistVideoLink",
    # Collection
    "CollectionCreate",
    "CollectionUpdate",
    "CollectionResponse",
    "CollectionVideoAdd",
    # Tag
    "TagCreate",
    "TagResponse",
    "TagsSet",
]
