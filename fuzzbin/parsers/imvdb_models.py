"""Pydantic models for IMVDb API responses."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# Custom Exceptions
class VideoNotFoundError(ValueError):
    """Raised when a video cannot be found matching the search criteria."""

    def __init__(
        self,
        artist: Optional[str] = None,
        title: Optional[str] = None,
        message: Optional[str] = None,
    ):
        """
        Initialize VideoNotFoundError.

        Args:
            artist: Artist name searched for
            title: Song title searched for
            message: Custom error message (overrides default)
        """
        if message:
            super().__init__(message)
        elif artist and title:
            super().__init__(f"Video not found for artist '{artist}' and title '{title}'")
        else:
            super().__init__("Video not found")
        self.artist = artist
        self.title = title


class EmptySearchResultsError(VideoNotFoundError):
    """Raised when search returns no results from the API."""

    def __init__(self, artist: Optional[str] = None, title: Optional[str] = None):
        """
        Initialize EmptySearchResultsError.

        Args:
            artist: Artist name searched for
            title: Song title searched for
        """
        if artist and title:
            message = f"Search returned no results for artist '{artist}' and title '{title}'"
        else:
            message = "Search returned no results"
        super().__init__(artist=artist, title=title, message=message)


# Pydantic Models
class IMVDbArtist(BaseModel):
    """Model for IMVDb artist information."""

    name: str = Field(description="Artist name")
    slug: Optional[str] = Field(default=None, description="URL-friendly slug")
    url: Optional[str] = Field(default=None, description="IMVDb profile URL")

    @field_validator("name", "slug", mode="before")
    @classmethod
    def coerce_to_string(cls, v: Any) -> Optional[str]:
        """Coerce integers and other types to strings (handles malformed IMVDb data)."""
        if v is None:
            return None
        return str(v)

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbSource(BaseModel):
    """Model for IMVDb video source (YouTube, Vimeo, etc.)."""

    source: str = Field(description="Source platform name")
    source_slug: str = Field(description="Source platform slug")
    source_data: Any = Field(description="Platform-specific video identifier")
    is_primary: bool = Field(description="Whether this is the primary source")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbDirector(BaseModel):
    """Model for IMVDb video director information."""

    position_name: str = Field(description="Position name (e.g., 'Director')")
    position_code: str = Field(description="Position code (e.g., 'dir')")
    entity_name: str = Field(description="Director name")
    entity_slug: str = Field(description="Director URL slug")
    entity_id: int = Field(description="Director entity ID")
    entity_url: str = Field(description="Director IMVDb profile URL")
    position_notes: Optional[str] = Field(default=None, description="Additional position notes")
    position_id: int = Field(description="Position record ID")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbCredit(BaseModel):
    """Model for IMVDb video crew credit."""

    position_name: str = Field(description="Position name")
    position_code: str = Field(description="Position code")
    entity_name: str = Field(description="Person/company name")
    entity_slug: str = Field(description="Entity URL slug")
    entity_id: int = Field(description="Entity ID")
    entity_url: str = Field(description="Entity IMVDb profile URL")
    position_notes: Optional[str] = Field(default=None, description="Additional position notes")
    position_id: int = Field(description="Position record ID")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbCast(BaseModel):
    """Model for IMVDb video cast member."""

    entity_name: str = Field(description="Cast member name")
    entity_slug: str = Field(description="Cast member URL slug")
    entity_id: int = Field(description="Cast member entity ID")
    cast_roles: List[str] = Field(default_factory=list, description="Roles played")
    position_id: int = Field(description="Position record ID")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbVideo(BaseModel):
    """Model for IMVDb video details."""

    id: int = Field(description="IMVDb video ID")
    song_title: Optional[str] = Field(default=None, description="Song title")
    year: Optional[int] = Field(default=None, description="Release year")
    artists: List[IMVDbArtist] = Field(default_factory=list, description="Primary artists")
    featured_artists: List[IMVDbArtist] = Field(
        default_factory=list, description="Featured artists"
    )
    directors: List[IMVDbDirector] = Field(default_factory=list, description="Directors")
    sources: List[IMVDbSource] = Field(default_factory=list, description="Video sources")
    production_status: Optional[str] = Field(default=None, description="Production status code")
    song_slug: Optional[str] = Field(default=None, description="Song URL slug")
    url: Optional[str] = Field(default=None, description="IMVDb video URL")
    multiple_versions: Optional[bool] = Field(
        default=None, description="Whether multiple versions exist"
    )
    version_name: Optional[str] = Field(default=None, description="Version name")
    version_number: Optional[int] = Field(default=None, description="Version number")
    is_imvdb_pick: Optional[bool] = Field(default=None, description="IMVDb pick status")
    aspect_ratio: Optional[str] = Field(default=None, description="Video aspect ratio")
    verified_credits: Optional[bool] = Field(
        default=None, description="Whether credits are verified"
    )
    image: Optional[Dict[str, Any]] = Field(default=None, description="Image URLs")
    credits: Optional[Dict[str, Any]] = Field(default=None, description="Full credits data")
    release_date_stamp: Optional[int] = Field(
        default=None, description="Release date Unix timestamp"
    )
    release_date_string: Optional[str] = Field(default=None, description="Release date string")
    is_exact_match: bool = Field(default=True, description="Whether this was an exact search match")

    @field_validator("song_title", "song_slug", mode="before")
    @classmethod
    def coerce_to_string(cls, v: Any) -> Optional[str]:
        """Coerce integers and other types to strings (handles malformed IMVDb data)."""
        if v is None:
            return None
        return str(v)

    @field_validator("year", mode="before")
    @classmethod
    def coerce_year(cls, v: Any) -> Optional[int]:
        """Coerce empty strings and invalid values to None for year field."""
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbEntityVideo(BaseModel):
    """Model for video in entity video list."""

    id: int = Field(description="IMVDb video ID")
    song_title: Optional[str] = Field(default=None, description="Song title")
    year: Optional[int] = Field(default=None, description="Release year")
    production_status: Optional[str] = Field(default=None, description="Production status code")
    song_slug: Optional[str] = Field(default=None, description="Song URL slug")
    url: Optional[str] = Field(default=None, description="IMVDb video URL")
    multiple_versions: Optional[bool] = Field(
        default=None, description="Whether multiple versions exist"
    )
    version_name: Optional[str] = Field(default=None, description="Version name")
    version_number: Optional[int] = Field(default=None, description="Version number")
    is_imvdb_pick: Optional[bool] = Field(default=None, description="IMVDb pick status")
    aspect_ratio: Optional[str] = Field(default=None, description="Video aspect ratio")
    verified_credits: Optional[bool] = Field(
        default=None, description="Whether credits are verified"
    )
    artists: List[IMVDbArtist] = Field(default_factory=list, description="Primary artists")
    image: Optional[Any] = Field(
        default=None, description="Image URLs (can be dict, list, or null)"
    )

    @field_validator("song_title", "song_slug", mode="before")
    @classmethod
    def coerce_to_string(cls, v: Any) -> Optional[str]:
        """Coerce integers and other types to strings (handles malformed IMVDb data)."""
        if v is None:
            return None
        return str(v)

    @field_validator("year", mode="before")
    @classmethod
    def coerce_year(cls, v: Any) -> Optional[int]:
        """Coerce empty strings and invalid values to None for year field."""
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbPagination(BaseModel):
    """Model for pagination metadata."""

    total_results: int = Field(description="Total number of results")
    current_page: int = Field(description="Current page number")
    per_page: int = Field(description="Results per page")
    total_pages: int = Field(description="Total number of pages")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbEntitySearchResult(BaseModel):
    """Model for individual entity in search results."""

    id: int = Field(description="IMVDb entity ID")
    name: Optional[str] = Field(default=None, description="Entity name")
    slug: Optional[str] = Field(default=None, description="Entity URL slug")
    url: Optional[str] = Field(default=None, description="Entity IMVDb profile URL")
    discogs_id: Optional[int] = Field(default=None, description="Discogs ID")
    byline: Optional[str] = Field(default=None, description="Entity byline")
    bio: Optional[str] = Field(default=None, description="Entity biography")
    image: Optional[str] = Field(default=None, description="Entity image URL")
    artist_video_count: Optional[int] = Field(
        default=None, description="Number of videos as primary artist"
    )
    featured_video_count: Optional[int] = Field(
        default=None, description="Number of videos as featured artist"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbEntity(BaseModel):
    """Model for IMVDb entity (artist/director/etc.) details."""

    id: int = Field(description="IMVDb entity ID")
    name: Optional[str] = Field(default=None, description="Entity name")
    slug: str = Field(description="Entity URL slug")
    url: str = Field(description="Entity IMVDb profile URL")
    discogs_id: Optional[int] = Field(default=None, description="Discogs ID")
    byline: Optional[str] = Field(default=None, description="Entity byline")
    bio: Optional[str] = Field(default=None, description="Entity biography")
    image: Optional[str] = Field(default=None, description="Entity image URL")
    artist_video_count: int = Field(description="Number of videos as primary artist")
    featured_video_count: int = Field(description="Number of videos as featured artist")
    artist_videos: List[IMVDbEntityVideo] = Field(
        default_factory=list, description="Videos as primary artist"
    )
    featured_artist_videos: List[IMVDbEntityVideo] = Field(
        default_factory=list, description="Videos as featured artist"
    )
    artist_videos_total: Optional[int] = Field(
        default=None, description="Total artist videos (for pagination)"
    )
    featured_videos_total: Optional[int] = Field(
        default=None, description="Total featured videos (for pagination)"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbVideoSearchResult(BaseModel):
    """Model for IMVDb video search results."""

    pagination: IMVDbPagination = Field(description="Pagination metadata")
    results: List[IMVDbEntityVideo] = Field(
        default_factory=list, description="Search result videos"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbEntitySearchResponse(BaseModel):
    """Model for IMVDb entity search results."""

    pagination: IMVDbPagination = Field(description="Pagination metadata")
    results: List[IMVDbEntitySearchResult] = Field(
        default_factory=list, description="Search result entities"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class IMVDbEntityVideosPage(BaseModel):
    """Model for paginated entity artist videos response.

    Used for lazy-loading artist videos in the artist import workflow.
    """

    entity_id: int = Field(description="IMVDb entity ID")
    entity_slug: Optional[str] = Field(default=None, description="Entity URL slug")
    entity_name: Optional[str] = Field(default=None, description="Entity display name")
    total_videos: int = Field(description="Total number of artist videos")
    current_page: int = Field(description="Current page number (1-indexed)")
    per_page: int = Field(description="Results per page")
    total_pages: int = Field(description="Total number of pages")
    has_more: bool = Field(description="Whether more pages are available")
    videos: List[IMVDbEntityVideo] = Field(default_factory=list, description="Videos for this page")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }
