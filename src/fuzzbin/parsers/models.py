"""Pydantic models for NFO file data structures."""

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ArtistNFO(BaseModel):
    """Model for artist.nfo file."""

    name: Optional[str] = Field(default=None, description="Artist name")

    model_config = {
        "extra": "ignore",  # Ignore unknown elements
        "validate_assignment": True,  # Validate on assignment for update operations
    }


class MusicVideoNFO(BaseModel):
    """Model for musicvideo.nfo file."""

    title: Optional[str] = Field(default=None, description="Video title")
    album: Optional[str] = Field(default=None, description="Album name")
    studio: Optional[str] = Field(default=None, description="Studio/label name")
    year: Optional[int] = Field(default=None, description="Release year")
    director: Optional[str] = Field(default=None, description="Video director")
    genre: Optional[str] = Field(default=None, description="Music genre")
    artist: Optional[str] = Field(default=None, description="Primary artist name")
    tags: List[str] = Field(default_factory=list, description="Video tags")

    model_config = {
        "extra": "ignore",  # Ignore unknown elements
        "validate_assignment": True,  # Validate on assignment
    }

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        """Validate year is reasonable if provided."""
        if v is not None and (v < 1900 or v > 2100):
            raise ValueError(f"Year must be between 1900 and 2100, got {v}")
        return v
