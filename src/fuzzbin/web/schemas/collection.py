"""Collection schemas for API request/response DTOs."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class CollectionBase(BaseModel):
    """Base collection fields shared across schemas."""

    name: Optional[str] = Field(
        default=None, max_length=255, description="Collection name"
    )
    description: Optional[str] = Field(
        default=None, description="Collection description"
    )


class CollectionCreate(CollectionBase):
    """Schema for creating a new collection."""

    name: str = Field(..., min_length=1, max_length=255, description="Collection name")

    def to_repo_kwargs(self) -> Dict[str, Any]:
        """Convert to keyword arguments for repository create method."""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class CollectionUpdate(CollectionBase):
    """Schema for updating an existing collection (all fields optional)."""

    def to_repo_kwargs(self) -> Dict[str, Any]:
        """Convert to keyword arguments for repository update method."""
        return {k: v for k, v in self.model_dump(exclude_unset=True).items()}


class CollectionResponse(CollectionBase):
    """Full collection response with all fields."""

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    # Computed field
    video_count: Optional[int] = Field(
        default=None, description="Number of videos in this collection"
    )

    model_config = {"from_attributes": True}

    @classmethod
    def from_db_row(
        cls, row: Dict[str, Any], video_count: Optional[int] = None
    ) -> "CollectionResponse":
        """
        Create CollectionResponse from database row.

        Args:
            row: Database row as dict
            video_count: Optional count of videos in collection

        Returns:
            CollectionResponse instance
        """
        data = dict(row)
        if video_count is not None:
            data["video_count"] = video_count
        return cls(**data)


class CollectionVideoAdd(BaseModel):
    """Schema for adding a video to a collection."""

    video_id: int = Field(..., description="Video ID to add")
    position: Optional[int] = Field(
        default=None, ge=0, description="Position in collection (optional)"
    )


class CollectionVideosResponse(BaseModel):
    """Response for collection's videos endpoint."""

    collection: CollectionResponse
    video_count: int
    # videos will be paginated separately
