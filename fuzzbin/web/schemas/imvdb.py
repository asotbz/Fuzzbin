"""Pydantic schemas for IMVDb API responses.

These schemas represent the upstream IMVDb API response structures,
allowing pass-through of external API data with proper typing.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IMVDbArtistRef(BaseModel):
    """Artist reference in IMVDb responses."""

    name: str = Field(description="Artist name")
    slug: Optional[str] = Field(default=None, description="URL-friendly slug")
    url: Optional[str] = Field(default=None, description="IMVDb profile URL")

    model_config = {"extra": "ignore"}


class IMVDbImageSet(BaseModel):
    """Image URLs at various sizes."""

    o: Optional[str] = Field(default=None, description="Original size")
    large: Optional[str] = Field(default=None, alias="l", description="Large size")
    b: Optional[str] = Field(default=None, description="Banner size")
    t: Optional[str] = Field(default=None, description="Thumbnail size")
    s: Optional[str] = Field(default=None, description="Small size")

    model_config = {"extra": "ignore"}


class IMVDbSource(BaseModel):
    """Video source (YouTube, Vimeo, etc.)."""

    source: str = Field(description="Source platform name")
    source_slug: str = Field(description="Source platform slug")
    source_data: Any = Field(description="Platform-specific video identifier")
    is_primary: bool = Field(default=False, description="Whether this is the primary source")

    model_config = {"extra": "ignore"}


class IMVDbCredit(BaseModel):
    """Crew credit entry."""

    position_name: str = Field(description="Position name (e.g., 'Director')")
    position_code: str = Field(description="Position code (e.g., 'dir')")
    entity_name: str = Field(description="Person/company name")
    entity_slug: str = Field(description="Entity URL slug")
    entity_id: int = Field(description="Entity ID")
    entity_url: str = Field(description="Entity IMVDb profile URL")
    position_notes: Optional[str] = Field(default=None, description="Additional notes")
    position_id: int = Field(description="Position record ID")

    model_config = {"extra": "ignore"}


class IMVDbCredits(BaseModel):
    """Credits container with crew and cast lists."""

    total_credits: int = Field(default=0, description="Total credit count")
    crew: List[IMVDbCredit] = Field(default_factory=list, description="Crew credits")
    cast: List[Dict[str, Any]] = Field(default_factory=list, description="Cast credits")

    model_config = {"extra": "ignore"}


# ==================== Video Search Response ====================


class IMVDbVideoSearchItem(BaseModel):
    """Video item in search results (summary, no credits)."""

    id: int = Field(description="IMVDb video ID")
    production_status: Optional[str] = Field(default=None, description="Production status code")
    song_title: Optional[str] = Field(default=None, description="Song title")
    song_slug: Optional[str] = Field(default=None, description="Song URL slug")
    url: Optional[str] = Field(default=None, description="IMVDb video URL")
    multiple_versions: Optional[bool] = Field(default=None, description="Has multiple versions")
    version_name: Optional[str] = Field(default=None, description="Version name")
    version_number: Optional[int] = Field(default=None, description="Version number")
    is_imvdb_pick: Optional[bool] = Field(default=None, description="Featured pick")
    aspect_ratio: Optional[str] = Field(default=None, description="Video aspect ratio")
    year: Optional[int] = Field(default=None, description="Release year")
    verified_credits: Optional[bool] = Field(default=None, description="Credits verified")
    artists: List[IMVDbArtistRef] = Field(default_factory=list, description="Primary artists")
    image: Optional[IMVDbImageSet] = Field(default=None, description="Thumbnail images")

    model_config = {"extra": "ignore"}


class IMVDbVideoSearchResponse(BaseModel):
    """Response from IMVDb video search endpoint."""

    total_results: int = Field(description="Total matching results")
    current_page: int = Field(description="Current page number")
    per_page: int = Field(description="Results per page")
    total_pages: int = Field(description="Total number of pages")
    results: List[IMVDbVideoSearchItem] = Field(default_factory=list, description="Video results")

    model_config = {"extra": "ignore"}


# ==================== Video Detail Response ====================


class IMVDbVideoDetail(BaseModel):
    """Full video details including credits and sources."""

    id: int = Field(description="IMVDb video ID")
    production_status: Optional[str] = Field(default=None, description="Production status code")
    song_title: Optional[str] = Field(default=None, description="Song title")
    song_slug: Optional[str] = Field(default=None, description="Song URL slug")
    url: Optional[str] = Field(default=None, description="IMVDb video URL")
    multiple_versions: Optional[bool] = Field(default=None, description="Has multiple versions")
    version_name: Optional[str] = Field(default=None, description="Version name")
    version_number: Optional[int] = Field(default=None, description="Version number")
    is_imvdb_pick: Optional[bool] = Field(default=None, description="Featured pick")
    aspect_ratio: Optional[str] = Field(default=None, description="Video aspect ratio")
    year: Optional[int] = Field(default=None, description="Release year")
    verified_credits: Optional[bool] = Field(default=None, description="Credits verified")
    artists: List[IMVDbArtistRef] = Field(default_factory=list, description="Primary artists")
    featured_artists: List[IMVDbArtistRef] = Field(
        default_factory=list, description="Featured artists"
    )
    image: Optional[IMVDbImageSet] = Field(default=None, description="Thumbnail images")
    sources: List[IMVDbSource] = Field(default_factory=list, description="Video sources")
    directors: List[IMVDbCredit] = Field(default_factory=list, description="Director credits")
    credits: Optional[IMVDbCredits] = Field(default=None, description="Full credits")

    model_config = {"extra": "ignore"}


# ==================== Entity Search Response ====================


class IMVDbEntitySearchItem(BaseModel):
    """Entity item in search results."""

    id: int = Field(description="IMVDb entity ID")
    name: Optional[str] = Field(default=None, description="Entity name")
    slug: Optional[str] = Field(default=None, description="URL slug")
    url: Optional[str] = Field(default=None, description="IMVDb profile URL")
    discogs_id: Optional[int] = Field(default=None, description="Linked Discogs ID")
    byline: Optional[str] = Field(default=None, description="Short description")
    bio: Optional[str] = Field(default=None, description="Biography")
    image: Optional[str] = Field(default=None, description="Profile image URL")
    artist_video_count: int = Field(default=0, description="Videos as primary artist")
    featured_video_count: int = Field(default=0, description="Videos as featured artist")

    model_config = {"extra": "ignore"}


class IMVDbEntitySearchResponse(BaseModel):
    """Response from IMVDb entity search endpoint."""

    total_results: int = Field(description="Total matching results")
    current_page: int = Field(description="Current page number")
    per_page: int = Field(description="Results per page")
    total_pages: int = Field(description="Total number of pages")
    results: List[IMVDbEntitySearchItem] = Field(default_factory=list, description="Entity results")

    model_config = {"extra": "ignore"}


# ==================== Entity Detail Response ====================


class IMVDbArtistVideos(BaseModel):
    """Container for entity's artist videos."""

    total_videos: int = Field(default=0, description="Total video count")
    videos: List[IMVDbVideoSearchItem] = Field(default_factory=list, description="Videos")

    model_config = {"extra": "ignore"}


class IMVDbEntityDetail(BaseModel):
    """Full entity details including video listings."""

    id: int = Field(description="IMVDb entity ID")
    name: Optional[str] = Field(default=None, description="Entity name")
    slug: Optional[str] = Field(default=None, description="URL slug")
    url: Optional[str] = Field(default=None, description="IMVDb profile URL")
    discogs_id: Optional[int] = Field(default=None, description="Linked Discogs ID")
    byline: Optional[str] = Field(default=None, description="Short description")
    bio: Optional[str] = Field(default=None, description="Biography")
    image: Optional[str] = Field(default=None, description="Profile image URL")
    artist_video_count: int = Field(default=0, description="Videos as primary artist")
    featured_video_count: int = Field(default=0, description="Videos as featured artist")
    artist_videos: Optional[IMVDbArtistVideos] = Field(
        default=None, description="Videos as primary artist"
    )
    featured_videos: Optional[IMVDbArtistVideos] = Field(
        default=None, description="Videos as featured artist"
    )

    model_config = {"extra": "ignore"}
