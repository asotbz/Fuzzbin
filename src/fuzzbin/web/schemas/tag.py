"""Tag schemas for API request/response DTOs."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    """Schema for creating a new tag."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Tag name (will be normalized)"
    )


class TagResponse(BaseModel):
    """Full tag response with all fields."""

    id: int
    name: str
    normalized_name: str = Field(description="Lowercase normalized tag name")
    created_at: datetime
    usage_count: int = Field(default=0, description="Number of videos with this tag")

    model_config = {"from_attributes": True}

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TagResponse":
        """
        Create TagResponse from database row.

        Args:
            row: Database row as dict

        Returns:
            TagResponse instance
        """
        return cls(**dict(row))


class TagsSet(BaseModel):
    """Schema for setting tags on a video (replaces existing)."""

    tags: List[str] = Field(
        ..., description="List of tag names to apply (will create if needed)"
    )
    source: Literal["manual", "auto"] = Field(
        default="manual", description="Tag source"
    )


class TagsAdd(BaseModel):
    """Schema for adding tags to a video (keeps existing)."""

    tags: List[str] = Field(
        ..., description="List of tag names to add (will create if needed)"
    )
    source: Literal["manual", "auto"] = Field(
        default="manual", description="Tag source"
    )


class VideoTagsResponse(BaseModel):
    """Response showing tags on a video."""

    video_id: int
    tags: List[TagResponse]
    total: int


class TagVideosResponse(BaseModel):
    """Response for tag's videos endpoint."""

    tag: TagResponse
    video_count: int
    # videos will be paginated separately
