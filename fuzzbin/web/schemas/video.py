"""Video schemas for API request/response DTOs."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Valid video status values
VIDEO_STATUSES = Literal[
    "discovered",
    "queued",
    "downloading",
    "downloaded",
    "imported",
    "organized",
    "missing",
    "failed",
    "archived",
]


class VideoBase(BaseModel):
    """Base video fields shared across schemas."""

    title: Optional[str] = Field(default=None, max_length=500, description="Video title")
    artist: Optional[str] = Field(default=None, max_length=255, description="Primary artist name")
    album: Optional[str] = Field(default=None, max_length=255, description="Album name")
    year: Optional[int] = Field(default=None, ge=1900, le=2100, description="Release year")
    director: Optional[str] = Field(default=None, max_length=255, description="Video director")
    genre: Optional[str] = Field(default=None, max_length=100, description="Music genre")
    studio: Optional[str] = Field(default=None, max_length=255, description="Production studio")


class VideoCreate(VideoBase):
    """Schema for creating a new video."""

    title: str = Field(..., min_length=1, max_length=500, description="Video title")

    # External IDs
    imvdb_video_id: Optional[str] = Field(default=None, max_length=50, description="IMVDb video ID")
    imvdb_url: Optional[str] = Field(
        default=None, max_length=500, description="Full IMVDb video URL"
    )
    youtube_id: Optional[str] = Field(default=None, max_length=50, description="YouTube video ID")
    vimeo_id: Optional[str] = Field(default=None, max_length=50, description="Vimeo video ID")

    # File paths (optional during creation)
    video_file_path: Optional[str] = Field(default=None, description="Absolute path to video file")
    nfo_file_path: Optional[str] = Field(default=None, description="Absolute path to NFO file")

    def to_repo_kwargs(self) -> Dict[str, Any]:
        """Convert to keyword arguments for repository create method."""
        return {
            k: v
            for k, v in self.model_dump().items()
            if v is not None and k not in ("video_file_path", "nfo_file_path")
        }


class VideoUpdate(VideoBase):
    """Schema for updating an existing video (all fields optional)."""

    imvdb_video_id: Optional[str] = Field(default=None, max_length=50, description="IMVDb video ID")
    imvdb_url: Optional[str] = Field(
        default=None, max_length=500, description="Full IMVDb video URL"
    )
    youtube_id: Optional[str] = Field(default=None, max_length=50, description="YouTube video ID")
    vimeo_id: Optional[str] = Field(default=None, max_length=50, description="Vimeo video ID")
    video_file_path: Optional[str] = Field(default=None, description="Absolute path to video file")
    nfo_file_path: Optional[str] = Field(default=None, description="Absolute path to NFO file")

    def to_repo_kwargs(self) -> Dict[str, Any]:
        """Convert to keyword arguments for repository update method."""
        # Only include explicitly set (non-None) values
        return {k: v for k, v in self.model_dump(exclude_unset=True).items()}


class VideoStatusUpdate(BaseModel):
    """Schema for updating video status."""

    status: VIDEO_STATUSES = Field(..., description="New video status")
    reason: Optional[str] = Field(
        default=None, max_length=500, description="Reason for status change"
    )
    changed_by: Optional[str] = Field(
        default=None, max_length=100, description="Who changed the status"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata for status change"
    )


class VideoArtistResponse(BaseModel):
    """Artist information embedded in video response."""

    id: int
    name: str
    role: str = Field(description="Artist role: 'primary' or 'featured'")
    position: int = Field(description="Position in credits order")


class VideoCollectionResponse(BaseModel):
    """Collection information embedded in video response."""

    id: int
    name: str
    position: Optional[int] = Field(description="Position in collection")


class VideoTagResponse(BaseModel):
    """Tag information embedded in video response."""

    id: int
    name: str
    source: str = Field(description="Tag source: 'manual' or 'auto'")


class VideoResponse(VideoBase):
    """Full video response with all fields and relationships."""

    id: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    # Status
    status: str = "discovered"
    status_changed_at: Optional[datetime] = None
    status_message: Optional[str] = None

    # External IDs
    imvdb_video_id: Optional[str] = None
    imvdb_url: Optional[str] = None
    youtube_id: Optional[str] = None
    vimeo_id: Optional[str] = None

    # File info
    video_file_path: Optional[str] = None
    video_file_path_relative: Optional[str] = None
    nfo_file_path: Optional[str] = None
    nfo_file_path_relative: Optional[str] = None
    file_size: Optional[int] = None
    file_checksum: Optional[str] = None
    file_verified_at: Optional[datetime] = None

    # Technical metadata (from FFProbe)
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    container_format: Optional[str] = None
    bitrate: Optional[int] = None
    frame_rate: Optional[float] = None
    audio_channels: Optional[int] = None
    audio_sample_rate: Optional[int] = None
    aspect_ratio: Optional[str] = None

    # Download info
    download_source: Optional[str] = None
    download_attempts: int = 0
    last_download_attempt_at: Optional[datetime] = None
    last_download_error: Optional[str] = None

    # Relationships (populated when requested)
    artists: List[VideoArtistResponse] = Field(default_factory=list)
    collections: List[VideoCollectionResponse] = Field(default_factory=list)
    tags: List[VideoTagResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @classmethod
    def from_db_row(
        cls,
        row: Dict[str, Any],
        artists: Optional[List[Dict[str, Any]]] = None,
        collections: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[Dict[str, Any]]] = None,
    ) -> "VideoResponse":
        """
        Create VideoResponse from database row and optional relationships.

        Args:
            row: Database row as dict
            artists: Optional list of artist dicts with role/position
            collections: Optional list of collection dicts with position
            tags: Optional list of tag dicts with source

        Returns:
            VideoResponse instance
        """
        data = dict(row)

        # Convert relationships to response models
        if artists:
            data["artists"] = [
                VideoArtistResponse(
                    id=a["id"],
                    name=a["name"],
                    role=a.get("role", "primary"),
                    position=a.get("position", 0),
                )
                for a in artists
            ]
        if collections:
            data["collections"] = [
                VideoCollectionResponse(
                    id=c["id"],
                    name=c["name"],
                    position=c.get("position"),
                )
                for c in collections
            ]
        if tags:
            data["tags"] = [
                VideoTagResponse(
                    id=t["id"],
                    name=t["name"],
                    source=t.get("source", "manual"),
                )
                for t in tags
            ]

        return cls(**data)


class VideoFilters(BaseModel):
    """Filter parameters for video list endpoint."""

    # Text filters (case-insensitive LIKE)
    title: Optional[str] = Field(default=None, description="Filter by title (partial match)")
    artist: Optional[str] = Field(default=None, description="Filter by artist name (partial match)")
    album: Optional[str] = Field(default=None, description="Filter by album name (partial match)")
    director: Optional[str] = Field(default=None, description="Filter by director (partial match)")
    genre: Optional[str] = Field(default=None, description="Filter by genre (partial match)")

    # Exact match filters
    status: Optional[VIDEO_STATUSES] = Field(default=None, description="Filter by status")
    year: Optional[int] = Field(default=None, description="Filter by exact year")
    year_min: Optional[int] = Field(default=None, ge=1900, description="Filter by minimum year")
    year_max: Optional[int] = Field(default=None, le=2100, description="Filter by maximum year")

    # External ID filters
    imvdb_video_id: Optional[str] = Field(default=None, description="Filter by IMVDb ID")
    youtube_id: Optional[str] = Field(default=None, description="Filter by YouTube ID")

    # Relationship filters
    collection_name: Optional[str] = Field(
        default=None, description="Filter by collection name (partial match)"
    )
    collection_id: Optional[int] = Field(default=None, description="Filter by collection ID")
    tag_name: Optional[str] = Field(default=None, description="Filter by tag name (partial match)")
    tag_id: Optional[int] = Field(default=None, description="Filter by tag ID")

    # Full-text search
    search: Optional[str] = Field(default=None, description="Full-text search query (FTS5)")

    # Soft-delete handling
    include_deleted: bool = Field(default=False, description="Include soft-deleted videos")

    def apply_to_query(self, query: Any) -> Any:
        """
        Apply filters to a VideoQuery instance.

        Args:
            query: VideoQuery instance from repository

        Returns:
            Modified VideoQuery with filters applied
        """
        if self.title:
            query = query.where_title(self.title)
        if self.artist:
            query = query.where_artist(self.artist)
        if self.album:
            query = query.where_album(self.album)
        if self.director:
            query = query.where_director(self.director)
        if self.genre:
            query = query.where_genre(self.genre)
        if self.status:
            query = query.where_status(self.status)
        if self.year:
            query = query.where_year(self.year)
        elif self.year_min is not None or self.year_max is not None:
            # Use year_range if either min or max is specified
            start = self.year_min or 1900
            end = self.year_max or 2100
            query = query.where_year_range(start, end)
        if self.imvdb_video_id:
            query = query.where_imvdb_id(self.imvdb_video_id)
        if self.youtube_id:
            query = query.where_youtube_id(self.youtube_id)
        if self.collection_name:
            query = query.where_collection(self.collection_name)
        if self.collection_id:
            query = query.where_collection_id(self.collection_id)
        if self.tag_name:
            query = query.where_tag(self.tag_name)
        if self.tag_id:
            query = query.where_tag_id(self.tag_id)
        if self.search:
            query = query.search(self.search)
        if self.include_deleted:
            query = query.include_deleted()

        return query
