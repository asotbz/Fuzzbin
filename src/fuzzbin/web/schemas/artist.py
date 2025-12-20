"""Artist schemas for API request/response DTOs."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class ArtistBase(BaseModel):
    """Base artist fields shared across schemas."""

    name: Optional[str] = Field(
        default=None, max_length=255, description="Artist name"
    )
    biography: Optional[str] = Field(default=None, description="Artist biography")
    image_url: Optional[str] = Field(
        default=None, max_length=500, description="URL to artist image"
    )


class ArtistCreate(ArtistBase):
    """Schema for creating or upserting an artist."""

    name: str = Field(..., min_length=1, max_length=255, description="Artist name")

    # External IDs
    imvdb_entity_id: Optional[str] = Field(
        default=None, max_length=50, description="IMVDb entity ID"
    )
    discogs_artist_id: Optional[int] = Field(
        default=None, description="Discogs artist ID"
    )

    def to_repo_kwargs(self) -> Dict[str, Any]:
        """Convert to keyword arguments for repository upsert method."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class ArtistUpdate(ArtistBase):
    """Schema for updating an existing artist (all fields optional)."""

    imvdb_entity_id: Optional[str] = Field(
        default=None, max_length=50, description="IMVDb entity ID"
    )
    discogs_artist_id: Optional[int] = Field(
        default=None, description="Discogs artist ID"
    )

    def to_repo_kwargs(self) -> Dict[str, Any]:
        """Convert to keyword arguments for repository update method."""
        return {k: v for k, v in self.model_dump(exclude_unset=True).items()}


class ArtistResponse(ArtistBase):
    """Full artist response with all fields."""

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    # External IDs
    imvdb_entity_id: Optional[str] = None
    discogs_artist_id: Optional[int] = None

    # Computed field (not stored, but useful)
    video_count: Optional[int] = Field(
        default=None, description="Number of videos by this artist"
    )

    model_config = {"from_attributes": True}

    @classmethod
    def from_db_row(
        cls, row: Dict[str, Any], video_count: Optional[int] = None
    ) -> "ArtistResponse":
        """
        Create ArtistResponse from database row.

        Args:
            row: Database row as dict
            video_count: Optional count of videos by this artist

        Returns:
            ArtistResponse instance
        """
        data = dict(row)
        if video_count is not None:
            data["video_count"] = video_count
        return cls(**data)


class ArtistVideoLink(BaseModel):
    """Schema for linking an artist to a video."""

    artist_id: int = Field(..., description="Artist ID to link")
    role: Literal["primary", "featured"] = Field(
        default="primary", description="Artist role on the video"
    )
    position: int = Field(
        default=0, ge=0, description="Position in credits order"
    )


class ArtistVideosResponse(BaseModel):
    """Response for artist's videos endpoint."""

    artist: ArtistResponse
    video_count: int
    # videos will be paginated separately
