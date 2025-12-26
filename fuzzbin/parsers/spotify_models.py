"""Pydantic models for Spotify Web API responses."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SpotifyArtist(BaseModel):
    """Spotify artist information (simplified)."""

    id: str = Field(description="Spotify artist ID")
    name: str = Field(description="Artist name")
    uri: str = Field(description="Spotify URI")
    href: Optional[str] = Field(default=None, description="API endpoint URL")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class SpotifyAlbum(BaseModel):
    """Spotify album information."""

    id: str = Field(description="Spotify album ID")
    name: str = Field(description="Album name")
    release_date: Optional[str] = Field(
        default=None, description="Release date (YYYY-MM-DD or YYYY)"
    )
    release_date_precision: Optional[str] = Field(
        default=None, description="Precision: year, month, day"
    )
    label: Optional[str] = Field(default=None, description="Record label")
    uri: str = Field(description="Spotify URI")
    images: List[Dict[str, Any]] = Field(default_factory=list, description="Album artwork images")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class SpotifyTrack(BaseModel):
    """Spotify track information."""

    id: str = Field(description="Spotify track ID")
    name: str = Field(description="Track name")
    uri: str = Field(description="Spotify URI")
    artists: List[SpotifyArtist] = Field(default_factory=list, description="Track artists")
    album: Optional[SpotifyAlbum] = Field(default=None, description="Album information")
    duration_ms: Optional[int] = Field(default=None, description="Track duration in milliseconds")
    popularity: Optional[int] = Field(default=None, description="Popularity score 0-100")
    explicit: Optional[bool] = Field(default=None, description="Explicit content flag")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class SpotifyPlaylistTrack(BaseModel):
    """Playlist track item (wraps track with added_at, added_by)."""

    track: SpotifyTrack = Field(description="Track object")
    added_at: Optional[str] = Field(default=None, description="Timestamp when added")
    added_by: Optional[Dict[str, Any]] = Field(default=None, description="User who added track")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class SpotifyPlaylistTracksResponse(BaseModel):
    """Response from /playlists/{id}/tracks endpoint."""

    href: str = Field(description="API endpoint for this page")
    items: List[SpotifyPlaylistTrack] = Field(
        default_factory=list, description="Playlist tracks on this page"
    )
    limit: int = Field(description="Maximum items per page")
    next: Optional[str] = Field(default=None, description="URL for next page")
    offset: int = Field(description="Offset of first item")
    previous: Optional[str] = Field(default=None, description="URL for previous page")
    total: int = Field(description="Total number of items")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class SpotifyPlaylist(BaseModel):
    """Spotify playlist metadata."""

    id: str = Field(description="Spotify playlist ID")
    name: str = Field(description="Playlist name")
    description: Optional[str] = Field(default=None, description="Playlist description")
    uri: str = Field(description="Spotify URI")
    owner: Optional[Dict[str, Any]] = Field(default=None, description="Playlist owner")
    tracks: Optional[SpotifyPlaylistTracksResponse] = Field(
        default=None, description="Tracks (if included)"
    )
    public: Optional[bool] = Field(default=None, description="Public visibility")
    collaborative: Optional[bool] = Field(default=None, description="Collaborative flag")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }
