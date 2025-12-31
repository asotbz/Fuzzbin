"""Schemas for the /add import hub.

This module provides a thin, UI-friendly contract that composes existing primitives:
- Spotify playlist metadata endpoints (/spotify/*)
- NFO scan preview/import endpoints (/scan/*)
- Background jobs (/jobs/* + /ws/jobs/{job_id})

Initial scope intentionally focuses on batch preview + job submission.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class AddBatchMode(str, Enum):
    """Batch preview mode."""

    SPOTIFY = "spotify"
    NFO = "nfo"


class BatchPreviewRequest(BaseModel):
    """Request to preview a batch import before submitting a job."""

    mode: AddBatchMode = Field(description="Batch mode: spotify or nfo")

    spotify_playlist_id: Optional[str] = Field(
        default=None,
        description="Spotify playlist ID, URI, or URL",
        examples=[
            "37i9dQZF1DXcBWIGoYBM5M",
            "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
            "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
        ],
    )
    nfo_directory: Optional[str] = Field(
        default=None,
        description="Directory path containing .nfo files",
        examples=["/media/old_library/Music Videos"],
    )

    recursive: bool = Field(default=True, description="Recursive scan (nfo mode only)")
    skip_existing: bool = Field(
        default=True,
        description="Skip items already in the library (applies to both modes)",
    )

    @model_validator(mode="after")
    def _validate_mode_fields(self) -> "BatchPreviewRequest":
        if self.mode == AddBatchMode.SPOTIFY and not self.spotify_playlist_id:
            raise ValueError("spotify_playlist_id is required when mode=spotify")
        if self.mode == AddBatchMode.NFO and not self.nfo_directory:
            raise ValueError("nfo_directory is required when mode=nfo")
        return self


class BatchPreviewItem(BaseModel):
    """Single row in a batch preview response."""

    kind: str = Field(description="Item kind: spotify_track or nfo")

    title: str = Field(description="Track/video title")
    artist: str = Field(description="Primary artist")

    album: Optional[str] = Field(default=None, description="Album name")
    year: Optional[int] = Field(default=None, description="Release year if known")
    label: Optional[str] = Field(default=None, description="Record label")

    already_exists: bool = Field(default=False, description="Whether item already exists")

    # Source-specific identifiers (optional)
    spotify_track_id: Optional[str] = Field(default=None, description="Spotify track ID")
    spotify_playlist_id: Optional[str] = Field(default=None, description="Spotify playlist ID")

    nfo_path: Optional[str] = Field(default=None, description="NFO file path (nfo mode)")


class BatchPreviewResponse(BaseModel):
    """Unified batch preview response for spotify/nfo."""

    mode: AddBatchMode = Field(description="Batch mode")

    items: list[BatchPreviewItem] = Field(default_factory=list, description="Preview items")
    total_count: int = Field(description="Total items found")
    existing_count: int = Field(description="Items already in the library")
    new_count: int = Field(description="Items not yet in the library")

    # Optional context
    playlist_name: Optional[str] = Field(default=None, description="Spotify playlist name")
    directory: Optional[str] = Field(default=None, description="NFO directory scanned")

    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra mode-specific data (kept minimal)",
    )


class SpotifyImportRequest(BaseModel):
    """Request to submit a Spotify playlist import job.

    Note: Current backend workflow imports playlist tracks into the DB (discovery-style).
    Download/search per-track is intentionally out of scope for the first iteration.
    """

    playlist_id: str = Field(
        description="Spotify playlist ID, URI, or URL",
        examples=[
            "37i9dQZF1DXcBWIGoYBM5M",
            "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
            "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
        ],
    )
    skip_existing: bool = Field(default=True, description="Skip tracks already in DB")
    initial_status: str = Field(
        default="discovered",
        description="Initial status for created video records",
        examples=["discovered", "imported"],
    )


class SpotifyImportResponse(BaseModel):
    """Response after submitting a Spotify import job."""

    job_id: str = Field(description="Background job ID")
    playlist_id: str = Field(description="Normalized Spotify playlist ID")
    status: str = Field(default="pending", description="Initial job status")


class NFOScanResponse(BaseModel):
    """Response after submitting an NFO scan job via /add.

    This mirrors the /scan endpoint behavior but lives under /add for UI cohesion.
    """

    job_id: str = Field(description="Background job ID")
    directory: str = Field(description="Directory being scanned")
    mode: str = Field(description="Import mode")
    initial_status: str = Field(description="Initial status for created video records")
    status: str = Field(default="pending", description="Initial job status")


_SPOTIFY_PLAYLIST_URL_RE = re.compile(r"open\.spotify\.com/playlist/(?P<id>[A-Za-z0-9]+)")


def normalize_spotify_playlist_id(value: str) -> str:
    """Normalize a Spotify playlist identifier.

    Accepts:
    - Raw playlist IDs
    - spotify:playlist:<id> URIs
    - https://open.spotify.com/playlist/<id>[?...] URLs
    """

    raw = (value or "").strip()
    if not raw:
        return raw

    if raw.startswith("spotify:playlist:"):
        return raw.split(":")[-1]

    match = _SPOTIFY_PLAYLIST_URL_RE.search(raw)
    if match:
        return match.group("id")

    # Remove query string if caller passed just the path fragment
    raw = raw.split("?")[0].split("#")[0]

    return raw


class AddSearchSource(str, Enum):
    """Single-video search/preview source."""

    IMVDB = "imvdb"
    DISCOGS_MASTER = "discogs_master"
    DISCOGS_RELEASE = "discogs_release"
    YOUTUBE = "youtube"


class AddSearchRequest(BaseModel):
    """Request to search across supported sources for a single video."""

    artist: str = Field(min_length=1, max_length=200, description="Artist name")
    track_title: str = Field(min_length=1, max_length=200, description="Track/song title")

    include_sources: Optional[list[AddSearchSource]] = Field(
        default=None,
        description="Optional allowlist of sources to search. If omitted, searches all available sources.",
    )

    imvdb_per_page: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max IMVDb results to return",
    )
    discogs_per_page: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Max Discogs results to return",
    )
    youtube_max_results: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Max YouTube (yt-dlp) results to return",
    )


class AddSearchResultItem(BaseModel):
    """Normalized search result across sources."""

    source: AddSearchSource = Field(description="Where this result came from")
    id: str = Field(
        description="Source-specific identifier (IMVDb id, Discogs master/release id, YouTube id)"
    )

    title: str = Field(description="Best-effort title")
    artist: Optional[str] = Field(default=None, description="Best-effort primary artist")
    year: Optional[int] = Field(default=None, description="Release year if known")
    url: Optional[str] = Field(default=None, description="Upstream URL if available")
    thumbnail: Optional[str] = Field(default=None, description="Thumbnail URL if available")

    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional source-specific fields (kept minimal)",
    )


class AddSearchSkippedSource(BaseModel):
    source: AddSearchSource = Field(description="Source that was skipped")
    reason: str = Field(description="Why it was skipped")


class AddSearchResponse(BaseModel):
    """Aggregated search response."""

    artist: str = Field(description="Artist search term")
    track_title: str = Field(description="Track/title search term")
    results: list[AddSearchResultItem] = Field(
        default_factory=list, description="Flattened results"
    )
    skipped: list[AddSearchSkippedSource] = Field(
        default_factory=list,
        description="Sources that were unavailable or failed",
    )

    counts: dict[str, int] = Field(
        default_factory=dict,
        description="Counts per source (keys match AddSearchSource values)",
    )


class AddPreviewResponse(BaseModel):
    """Preview payload for a selected result."""

    source: AddSearchSource = Field(description="Preview source")
    id: str = Field(description="Source-specific identifier")
    data: dict[str, Any] = Field(description="Upstream-shaped data for rendering a preview")
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra cross-reference hints (kept minimal)",
    )


class AddSingleImportRequest(BaseModel):
    """Submit a single-video import job based on a selected search result."""

    source: AddSearchSource = Field(description="Selected source")
    id: str = Field(description="Selected item id (source-specific)")

    # Optional hints
    youtube_id: Optional[str] = Field(
        default=None,
        description="Optional YouTube video id to associate with the record (takes precedence over inferred ids)",
    )
    youtube_url: Optional[str] = Field(
        default=None,
        description="Optional YouTube URL to resolve via yt-dlp (used when source=youtube or to pin a specific video)",
    )

    initial_status: str = Field(
        default="discovered",
        description="Initial status for the created/updated video record",
        examples=["discovered", "imported"],
    )
    skip_existing: bool = Field(
        default=True,
        description="Skip creating a new record if a matching record already exists",
    )
    auto_download: bool = Field(
        default=True,
        description="Queue download job after import",
    )


class AddSingleImportResponse(BaseModel):
    """Response after submitting a single-video import job."""

    job_id: str = Field(description="Background job id")
    source: AddSearchSource = Field(description="Selected source")
    id: str = Field(description="Selected item id")
    status: str = Field(default="pending", description="Initial job status")


# Enhanced Spotify import schemas (interactive workflow)


class SpotifyTrackEnrichRequest(BaseModel):
    """Request to enrich a single Spotify track with IMVDb metadata."""

    artist: str = Field(min_length=1, max_length=200, description="Track artist name")
    track_title: str = Field(min_length=1, max_length=200, description="Track title")
    spotify_track_id: str = Field(description="Spotify track ID")
    album: Optional[str] = Field(default=None, description="Album name")
    year: Optional[int] = Field(default=None, description="Release year")
    label: Optional[str] = Field(default=None, description="Record label")


class SpotifyTrackEnrichResponse(BaseModel):
    """Response after enriching a Spotify track with IMVDb metadata."""

    spotify_track_id: str = Field(description="Spotify track ID")
    match_found: bool = Field(description="Whether an IMVDb match was found")
    match_type: Optional[str] = Field(
        default=None,
        description="Match type: 'exact' or 'fuzzy'",
    )
    imvdb_id: Optional[int] = Field(default=None, description="IMVDb video ID if match found")
    youtube_ids: list[str] = Field(
        default_factory=list,
        description="YouTube video IDs extracted from IMVDb sources",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Enriched metadata (title, artist, year, album, directors, sources)",
    )
    already_exists: bool = Field(
        default=False,
        description="Whether this track already exists in the library",
    )
    existing_video_id: Optional[int] = Field(
        default=None,
        description="Video ID if track already exists",
    )


class SelectedTrackImport(BaseModel):
    """Single track to import with optional metadata overrides."""

    spotify_track_id: str = Field(description="Spotify track ID")
    metadata: dict[str, Any] = Field(
        description="Track metadata (title, artist, year, album, directors)"
    )
    imvdb_id: Optional[int] = Field(default=None, description="IMVDb video ID if matched")
    youtube_id: Optional[str] = Field(default=None, description="YouTube video ID")
    youtube_url: Optional[str] = Field(default=None, description="YouTube URL")
    thumbnail_url: Optional[str] = Field(
        default=None, description="Thumbnail image URL to download"
    )


class SpotifyBatchImportRequest(BaseModel):
    """Request to import selected tracks from a Spotify playlist."""

    playlist_id: str = Field(
        description="Spotify playlist ID, URI, or URL",
        examples=[
            "37i9dQZF1DXcBWIGoYBM5M",
            "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
            "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
        ],
    )
    tracks: list[SelectedTrackImport] = Field(description="Selected tracks to import")
    initial_status: str = Field(
        default="discovered",
        description="Initial status for created video records",
        examples=["discovered", "imported"],
    )
    auto_download: bool = Field(
        default=False,
        description="Automatically queue download jobs for tracks with YouTube IDs",
    )


class SpotifyBatchImportResponse(BaseModel):
    """Response after submitting a batch Spotify import job."""

    job_id: str = Field(description="Background job ID")
    playlist_id: str = Field(description="Normalized Spotify playlist ID")
    track_count: int = Field(description="Number of tracks being imported")
    auto_download: bool = Field(description="Whether auto-download is enabled")
    status: str = Field(default="pending", description="Initial job status")


class YouTubeSearchRequest(BaseModel):
    """Request to search YouTube for videos."""

    artist: str = Field(min_length=1, max_length=200, description="Artist name")
    track_title: str = Field(min_length=1, max_length=200, description="Track title")
    max_results: int = Field(
        default=10,
        ge=1,
        le=25,
        description="Maximum number of results to return",
    )


class YouTubeMetadataRequest(BaseModel):
    """Request to fetch YouTube video metadata using yt-dlp."""

    youtube_id: str = Field(description="YouTube video ID")


class YouTubeMetadataResponse(BaseModel):
    """Response with YouTube video metadata from yt-dlp."""

    youtube_id: str = Field(description="YouTube video ID")
    available: bool = Field(description="Whether the video is available")
    view_count: Optional[int] = Field(default=None, description="View count")
    duration: Optional[int] = Field(default=None, description="Duration in seconds")
    channel: Optional[str] = Field(default=None, description="Channel name")
    title: Optional[str] = Field(default=None, description="Video title")
    error: Optional[str] = Field(default=None, description="Error message if unavailable")
