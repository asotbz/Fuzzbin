"""Pydantic schemas for API request/response DTOs."""

from .common import PageParams, PaginatedResponse, SortParams
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
