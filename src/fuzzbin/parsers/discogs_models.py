"""Pydantic models for Discogs API responses."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# Custom Exceptions
class MasterNotFoundError(ValueError):
    """Raised when a master release cannot be found matching the search criteria."""

    def __init__(
        self,
        master_id: Optional[int] = None,
        artist: Optional[str] = None,
        title: Optional[str] = None,
        message: Optional[str] = None,
    ):
        """
        Initialize MasterNotFoundError.

        Args:
            master_id: Master release ID searched for
            artist: Artist name searched for
            title: Track title searched for
            message: Custom error message (overrides default)
        """
        if message:
            super().__init__(message)
        elif master_id:
            super().__init__(f"Master release not found for master_id {master_id}")
        elif artist and title:
            super().__init__(
                f"Master release not found for artist '{artist}' and title '{title}'"
            )
        else:
            super().__init__("Master release not found")
        self.master_id = master_id
        self.artist = artist
        self.title = title


class ReleaseNotFoundError(ValueError):
    """Raised when a release cannot be found matching the search criteria."""

    def __init__(
        self,
        release_id: Optional[int] = None,
        artist: Optional[str] = None,
        title: Optional[str] = None,
        message: Optional[str] = None,
    ):
        """
        Initialize ReleaseNotFoundError.

        Args:
            release_id: Release ID searched for
            artist: Artist name searched for
            title: Track title searched for
            message: Custom error message (overrides default)
        """
        if message:
            super().__init__(message)
        elif release_id:
            super().__init__(f"Release not found for release_id {release_id}")
        elif artist and title:
            super().__init__(
                f"Release not found for artist '{artist}' and title '{title}'"
            )
        else:
            super().__init__("Release not found")
        self.release_id = release_id
        self.artist = artist
        self.title = title


class EmptySearchResultsError(ValueError):
    """Raised when search returns no results from the API."""

    def __init__(self, artist: Optional[str] = None, title: Optional[str] = None):
        """
        Initialize EmptySearchResultsError.

        Args:
            artist: Artist name searched for
            title: Track title searched for
        """
        if artist and title:
            message = f"Search returned no results for artist '{artist}' and title '{title}'"
        elif artist:
            message = f"Search returned no results for artist '{artist}'"
        else:
            message = "Search returned no results"
        super().__init__(message)
        self.artist = artist
        self.title = title


# Pydantic Models
class DiscogsPagination(BaseModel):
    """Model for Discogs pagination metadata."""

    page: int = Field(description="Current page number")
    pages: int = Field(description="Total number of pages")
    per_page: int = Field(description="Results per page")
    items: int = Field(description="Total number of items")
    urls: Optional[Dict[str, str]] = Field(
        default=None, description="URLs for pagination navigation"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsArtist(BaseModel):
    """Model for Discogs artist information."""

    name: str = Field(description="Artist name")
    id: int = Field(description="Discogs artist ID")
    anv: Optional[str] = Field(
        default=None, description="Artist name variation on this release"
    )
    join: Optional[str] = Field(
        default=None, description="Join phrase connecting to next artist"
    )
    role: Optional[str] = Field(default=None, description="Artist role on this release")
    tracks: Optional[str] = Field(
        default=None, description="Tracks this artist appears on"
    )
    resource_url: Optional[str] = Field(
        default=None, description="API URL for artist details"
    )
    thumbnail_url: Optional[str] = Field(
        default=None, description="Artist thumbnail image URL"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsTrack(BaseModel):
    """Model for Discogs track information."""

    position: str = Field(description="Track position (e.g., 'A1', '1', '1-1')")
    type_: str = Field(description="Track type (track, heading, index)")
    title: str = Field(description="Track title")
    duration: Optional[str] = Field(default=None, description="Track duration")
    extraartists: List[DiscogsArtist] = Field(
        default_factory=list, description="Featured/guest artists on this track"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsImage(BaseModel):
    """Model for Discogs image information."""

    type: str = Field(description="Image type (primary, secondary)")
    uri: str = Field(description="Full size image URL")
    resource_url: str = Field(description="Image resource URL")
    uri150: str = Field(description="150px thumbnail URL")
    width: int = Field(description="Image width in pixels")
    height: int = Field(description="Image height in pixels")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsVideo(BaseModel):
    """Model for Discogs video information."""

    uri: str = Field(description="Video URL (typically YouTube)")
    title: str = Field(description="Video title")
    description: Optional[str] = Field(default=None, description="Video description")
    duration: int = Field(description="Video duration in seconds")
    embed: bool = Field(description="Whether video can be embedded")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsLabel(BaseModel):
    """Model for Discogs label information."""

    name: str = Field(description="Label name")
    catno: str = Field(description="Catalog number")
    entity_type: Optional[str] = Field(default=None, description="Entity type code")
    entity_type_name: Optional[str] = Field(
        default=None, description="Entity type name"
    )
    id: int = Field(description="Discogs label ID")
    resource_url: Optional[str] = Field(
        default=None, description="API URL for label details"
    )
    thumbnail_url: Optional[str] = Field(
        default=None, description="Label thumbnail image URL"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsMaster(BaseModel):
    """Model for Discogs master release details."""

    id: int = Field(description="Discogs master release ID")
    title: str = Field(description="Release title")
    artists: List[DiscogsArtist] = Field(
        default_factory=list, description="Main artists"
    )
    year: Optional[int] = Field(default=None, description="Original release year")
    genres: List[str] = Field(default_factory=list, description="Music genres")
    styles: List[str] = Field(default_factory=list, description="Music styles")
    tracklist: List[DiscogsTrack] = Field(
        default_factory=list, description="Album tracklist"
    )
    images: List[DiscogsImage] = Field(default_factory=list, description="Cover images")
    videos: List[DiscogsVideo] = Field(
        default_factory=list, description="Associated videos"
    )
    main_release: Optional[int] = Field(
        default=None, description="Main release ID for this master"
    )
    main_release_url: Optional[str] = Field(
        default=None, description="API URL for main release"
    )
    resource_url: Optional[str] = Field(
        default=None, description="API URL for this master"
    )
    uri: Optional[str] = Field(default=None, description="Discogs web URL")
    data_quality: Optional[str] = Field(
        default=None, description="Data quality rating"
    )
    is_exact_match: bool = Field(
        default=True,
        description="Whether artist/track validation matched exactly",
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsRelease(BaseModel):
    """Model for Discogs release details."""

    id: int = Field(description="Discogs release ID")
    title: str = Field(description="Release title")
    artists: List[DiscogsArtist] = Field(
        default_factory=list, description="Main artists"
    )
    year: Optional[int] = Field(default=None, description="Release year")
    released: Optional[str] = Field(
        default=None, description="Exact release date string"
    )
    country: Optional[str] = Field(default=None, description="Release country")
    genres: List[str] = Field(default_factory=list, description="Music genres")
    styles: List[str] = Field(default_factory=list, description="Music styles")
    tracklist: List[DiscogsTrack] = Field(
        default_factory=list, description="Album tracklist"
    )
    labels: List[DiscogsLabel] = Field(
        default_factory=list, description="Record labels"
    )
    images: List[DiscogsImage] = Field(default_factory=list, description="Cover images")
    videos: List[DiscogsVideo] = Field(
        default_factory=list, description="Associated videos"
    )
    master_id: Optional[int] = Field(
        default=None, description="Master release ID this belongs to"
    )
    master_url: Optional[str] = Field(
        default=None, description="API URL for master release"
    )
    resource_url: Optional[str] = Field(
        default=None, description="API URL for this release"
    )
    uri: Optional[str] = Field(default=None, description="Discogs web URL")
    data_quality: Optional[str] = Field(
        default=None, description="Data quality rating"
    )
    is_exact_match: bool = Field(
        default=True,
        description="Whether artist/track validation matched exactly",
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsSearchResultItem(BaseModel):
    """Model for individual item in Discogs search results."""

    id: int = Field(description="Release or master ID")
    type: str = Field(description="Result type (master, release)")
    title: str = Field(description="Result title")
    master_id: Optional[int] = Field(
        default=None, description="Master release ID (for master types)"
    )
    master_url: Optional[str] = Field(
        default=None, description="API URL for master release"
    )
    uri: Optional[str] = Field(default=None, description="Discogs web URL")
    resource_url: Optional[str] = Field(
        default=None, description="API URL for this result"
    )
    thumb: Optional[str] = Field(default=None, description="Thumbnail image URL")
    cover_image: Optional[str] = Field(default=None, description="Cover image URL")
    country: Optional[str] = Field(default=None, description="Release country")
    year: Optional[str] = Field(default=None, description="Release year")
    format: List[str] = Field(default_factory=list, description="Release formats")
    label: List[str] = Field(default_factory=list, description="Record labels")
    genre: List[str] = Field(default_factory=list, description="Music genres")
    style: List[str] = Field(default_factory=list, description="Music styles")
    catno: Optional[str] = Field(default=None, description="Catalog number")
    barcode: List[str] = Field(default_factory=list, description="Barcodes")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsSearchResult(BaseModel):
    """Model for Discogs search results."""

    pagination: DiscogsPagination = Field(description="Pagination metadata")
    results: List[DiscogsSearchResultItem] = Field(
        default_factory=list, description="Search result items"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsArtistRelease(BaseModel):
    """Model for release in artist releases list."""

    id: int = Field(description="Release or master ID")
    type: str = Field(description="Release type (master, release)")
    title: str = Field(description="Release title")
    artist: str = Field(description="Artist name")
    year: Optional[int] = Field(default=None, description="Release year")
    role: Optional[str] = Field(default=None, description="Artist role")
    main_release: Optional[int] = Field(
        default=None, description="Main release ID (for master types)"
    )
    resource_url: Optional[str] = Field(
        default=None, description="API URL for this release"
    )
    thumb: Optional[str] = Field(default=None, description="Thumbnail image URL")
    format: Optional[str] = Field(default=None, description="Release format")
    label: Optional[str] = Field(default=None, description="Record label")
    status: Optional[str] = Field(default=None, description="Release status")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }


class DiscogsArtistReleasesResult(BaseModel):
    """Model for artist releases list response."""

    pagination: DiscogsPagination = Field(description="Pagination metadata")
    releases: List[DiscogsArtistRelease] = Field(
        default_factory=list, description="Artist releases"
    )

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }
