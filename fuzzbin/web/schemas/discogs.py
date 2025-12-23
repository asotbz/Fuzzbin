"""Pydantic schemas for Discogs API responses.

These schemas represent the upstream Discogs API response structures,
allowing pass-through of external API data with proper typing.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ==================== Common Components ====================


class DiscogsPagination(BaseModel):
    """Pagination metadata from Discogs API."""

    page: int = Field(description="Current page number")
    pages: int = Field(description="Total number of pages")
    per_page: int = Field(description="Results per page")
    items: int = Field(description="Total item count")
    urls: Dict[str, str] = Field(default_factory=dict, description="Navigation URLs")

    model_config = {"extra": "ignore"}


class DiscogsCommunity(BaseModel):
    """Community stats for a release."""

    want: int = Field(default=0, description="Users who want this")
    have: int = Field(default=0, description="Users who have this")

    model_config = {"extra": "ignore"}


class DiscogsImage(BaseModel):
    """Image metadata."""

    type: str = Field(description="Image type (primary, secondary)")
    uri: str = Field(description="Full-size image URL")
    resource_url: str = Field(description="API resource URL")
    uri150: Optional[str] = Field(default=None, description="150px thumbnail URL")
    width: int = Field(description="Image width")
    height: int = Field(description="Image height")

    model_config = {"extra": "ignore"}


class DiscogsTrack(BaseModel):
    """Track listing entry."""

    position: str = Field(description="Track position (e.g., 'A1', '1')")
    type_: str = Field(alias="type_", description="Entry type (track, heading, index)")
    title: str = Field(description="Track title")
    duration: Optional[str] = Field(default=None, description="Duration string")
    extraartists: List[Dict[str, Any]] = Field(
        default_factory=list, description="Additional artists"
    )

    model_config = {"extra": "ignore", "populate_by_name": True}


class DiscogsVideo(BaseModel):
    """Video link from release."""

    uri: str = Field(description="Video URL")
    title: str = Field(description="Video title")
    description: Optional[str] = Field(default=None, description="Video description")
    duration: int = Field(default=0, description="Duration in seconds")
    embed: bool = Field(default=False, description="Embeddable")

    model_config = {"extra": "ignore"}


class DiscogsArtistRef(BaseModel):
    """Artist reference in release data."""

    id: int = Field(description="Discogs artist ID")
    name: str = Field(description="Artist name")
    resource_url: str = Field(description="API resource URL")
    anv: Optional[str] = Field(default=None, description="Artist name variation")
    join: Optional[str] = Field(default=None, description="Join phrase")
    role: Optional[str] = Field(default=None, description="Role")
    tracks: Optional[str] = Field(default=None, description="Track numbers")

    model_config = {"extra": "ignore"}


# ==================== Search Response ====================


class DiscogsSearchResult(BaseModel):
    """Individual search result item."""

    id: int = Field(description="Master/Release ID")
    type: str = Field(description="Result type (master, release, artist)")
    master_id: Optional[int] = Field(default=None, description="Master release ID")
    master_url: Optional[str] = Field(default=None, description="Master API URL")
    uri: str = Field(description="Discogs web URI")
    title: str = Field(description="Title (Artist - Release)")
    country: Optional[str] = Field(default=None, description="Release country")
    year: Optional[str] = Field(default=None, description="Release year")
    format: List[str] = Field(default_factory=list, description="Release formats")
    label: List[str] = Field(default_factory=list, description="Record labels")
    genre: List[str] = Field(default_factory=list, description="Genres")
    style: List[str] = Field(default_factory=list, description="Styles")
    catno: Optional[str] = Field(default=None, description="Catalog number")
    barcode: List[str] = Field(default_factory=list, description="Barcodes")
    thumb: Optional[str] = Field(default=None, description="Thumbnail URL")
    cover_image: Optional[str] = Field(default=None, description="Cover image URL")
    resource_url: str = Field(description="API resource URL")
    community: Optional[DiscogsCommunity] = Field(default=None, description="Community stats")

    model_config = {"extra": "ignore"}


class DiscogsSearchResponse(BaseModel):
    """Response from Discogs search endpoint."""

    pagination: DiscogsPagination = Field(description="Pagination metadata")
    results: List[DiscogsSearchResult] = Field(default_factory=list, description="Search results")

    model_config = {"extra": "ignore"}


# ==================== Master Response ====================


class DiscogsMaster(BaseModel):
    """Master release details."""

    id: int = Field(description="Master ID")
    main_release: int = Field(description="Main release ID")
    most_recent_release: Optional[int] = Field(default=None, description="Most recent release ID")
    resource_url: str = Field(description="API resource URL")
    uri: str = Field(description="Discogs web URL")
    versions_url: str = Field(description="Versions list API URL")
    main_release_url: str = Field(description="Main release API URL")
    most_recent_release_url: Optional[str] = Field(
        default=None, description="Most recent release API URL"
    )
    num_for_sale: int = Field(default=0, description="Copies for sale")
    lowest_price: Optional[float] = Field(default=None, description="Lowest sale price")
    images: List[DiscogsImage] = Field(default_factory=list, description="Cover images")
    genres: List[str] = Field(default_factory=list, description="Genres")
    styles: List[str] = Field(default_factory=list, description="Styles")
    year: Optional[int] = Field(default=None, description="Release year")
    tracklist: List[DiscogsTrack] = Field(default_factory=list, description="Track listing")
    artists: List[DiscogsArtistRef] = Field(default_factory=list, description="Artists")
    title: Optional[str] = Field(default=None, description="Release title")
    data_quality: Optional[str] = Field(default=None, description="Data quality rating")
    videos: List[DiscogsVideo] = Field(default_factory=list, description="Related videos")

    model_config = {"extra": "ignore"}


# ==================== Release Response ====================


class DiscogsLabel(BaseModel):
    """Label information."""

    id: int = Field(description="Label ID")
    name: str = Field(description="Label name")
    catno: Optional[str] = Field(default=None, description="Catalog number")
    entity_type: Optional[str] = Field(default=None, description="Entity type")
    entity_type_name: Optional[str] = Field(default=None, description="Entity type name")
    resource_url: str = Field(description="API resource URL")

    model_config = {"extra": "ignore"}


class DiscogsFormat(BaseModel):
    """Release format details."""

    name: str = Field(description="Format name")
    qty: str = Field(description="Quantity")
    text: Optional[str] = Field(default=None, description="Additional text")
    descriptions: List[str] = Field(default_factory=list, description="Format descriptions")

    model_config = {"extra": "ignore"}


class DiscogsIdentifier(BaseModel):
    """Release identifier (barcode, matrix, etc.)."""

    type: str = Field(description="Identifier type")
    value: str = Field(description="Identifier value")
    description: Optional[str] = Field(default=None, description="Description")

    model_config = {"extra": "ignore"}


class DiscogsRelease(BaseModel):
    """Full release details."""

    id: int = Field(description="Release ID")
    status: Optional[str] = Field(default=None, description="Release status")
    year: Optional[int] = Field(default=None, description="Release year")
    resource_url: str = Field(description="API resource URL")
    uri: str = Field(description="Discogs web URL")
    artists: List[DiscogsArtistRef] = Field(default_factory=list, description="Artists")
    artists_sort: Optional[str] = Field(default=None, description="Sorted artist names")
    labels: List[DiscogsLabel] = Field(default_factory=list, description="Record labels")
    formats: List[DiscogsFormat] = Field(default_factory=list, description="Release formats")
    community: Optional[DiscogsCommunity] = Field(default=None, description="Community stats")
    format_quantity: int = Field(default=1, description="Number of format items")
    date_added: Optional[str] = Field(default=None, description="Date added to Discogs")
    date_changed: Optional[str] = Field(default=None, description="Date last modified")
    num_for_sale: int = Field(default=0, description="Copies for sale")
    lowest_price: Optional[float] = Field(default=None, description="Lowest sale price")
    master_id: Optional[int] = Field(default=None, description="Master release ID")
    master_url: Optional[str] = Field(default=None, description="Master API URL")
    title: str = Field(description="Release title")
    country: Optional[str] = Field(default=None, description="Release country")
    released: Optional[str] = Field(default=None, description="Release date string")
    released_formatted: Optional[str] = Field(default=None, description="Formatted release date")
    notes: Optional[str] = Field(default=None, description="Release notes")
    identifiers: List[DiscogsIdentifier] = Field(default_factory=list, description="Identifiers")
    videos: List[DiscogsVideo] = Field(default_factory=list, description="Related videos")
    genres: List[str] = Field(default_factory=list, description="Genres")
    styles: List[str] = Field(default_factory=list, description="Styles")
    tracklist: List[DiscogsTrack] = Field(default_factory=list, description="Track listing")
    extraartists: List[DiscogsArtistRef] = Field(
        default_factory=list, description="Additional credits"
    )
    images: List[DiscogsImage] = Field(default_factory=list, description="Cover images")
    thumb: Optional[str] = Field(default=None, description="Thumbnail URL")
    estimated_weight: Optional[int] = Field(default=None, description="Estimated weight (g)")
    data_quality: Optional[str] = Field(default=None, description="Data quality rating")

    model_config = {"extra": "ignore"}


# ==================== Artist Releases Response ====================


class DiscogsArtistRelease(BaseModel):
    """Release item in artist's discography."""

    id: int = Field(description="Release/Master ID")
    type: str = Field(description="Type (release, master)")
    main_release: Optional[int] = Field(default=None, description="Main release ID (for masters)")
    artist: str = Field(description="Artist name")
    title: str = Field(description="Release title")
    year: Optional[int] = Field(default=None, description="Release year")
    resource_url: str = Field(description="API resource URL")
    role: str = Field(description="Artist role (Main, Remix, etc.)")
    thumb: Optional[str] = Field(default=None, description="Thumbnail URL")
    status: Optional[str] = Field(default=None, description="Release status")
    format: Optional[str] = Field(default=None, description="Release format")
    label: Optional[str] = Field(default=None, description="Record label")
    stats: Optional[Dict[str, Any]] = Field(default=None, description="Community stats")

    model_config = {"extra": "ignore"}


class DiscogsArtistReleasesResponse(BaseModel):
    """Response from artist releases endpoint."""

    pagination: DiscogsPagination = Field(description="Pagination metadata")
    releases: List[DiscogsArtistRelease] = Field(
        default_factory=list, description="Artist's releases"
    )

    model_config = {"extra": "ignore"}
