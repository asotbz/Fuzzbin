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
    isrc: Optional[str] = Field(
        default=None,
        description="ISRC code from Spotify for MusicBrainz lookup and duplicate detection",
    )

    already_exists: bool = Field(default=False, description="Whether item already exists")

    # Source-specific identifiers (optional)
    spotify_track_id: Optional[str] = Field(default=None, description="Spotify track ID")
    spotify_playlist_id: Optional[str] = Field(default=None, description="Spotify playlist ID")
    spotify_artist_id: Optional[str] = Field(
        default=None, description="Primary artist Spotify ID (for genre lookup)"
    )
    artist_genres: Optional[list[str]] = Field(
        default=None,
        description="Genres from Spotify for the primary artist",
    )

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

    # Pre-fetched metadata (avoids redundant API calls if already fetched during search/preview)
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Pre-fetched metadata from search/preview step. If provided, skips re-fetching from source API. Expected fields: title, artist, year, director, genre, label, featured_artists",
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
    """Request for unified track enrichment (MusicBrainz + IMVDb)."""

    spotify_track_id: str = Field(description="Spotify track ID")
    artist: str = Field(min_length=1, max_length=200, description="Track artist name")
    track_title: str = Field(min_length=1, max_length=200, description="Track title")
    isrc: Optional[str] = Field(
        default=None,
        description="ISRC from Spotify for MusicBrainz lookup",
    )
    album: Optional[str] = Field(default=None, description="Spotify album name for fallback")
    artist_genres: Optional[list[str]] = Field(
        default=None,
        description="Spotify artist genres (used as fallback when MusicBrainz returns no genre)",
    )


class MusicBrainzEnrichmentData(BaseModel):
    """MusicBrainz enrichment results."""

    recording_mbid: Optional[str] = Field(default=None, description="MusicBrainz recording MBID")
    release_mbid: Optional[str] = Field(default=None, description="MusicBrainz release MBID")
    canonical_title: Optional[str] = Field(
        default=None,
        description="Canonical track title from MusicBrainz",
    )
    canonical_artist: Optional[str] = Field(
        default=None,
        description="Canonical artist name from MusicBrainz",
    )
    album: Optional[str] = Field(default=None, description="Album name from MusicBrainz")
    year: Optional[int] = Field(default=None, description="Release year from MusicBrainz")
    label: Optional[str] = Field(default=None, description="Record label from MusicBrainz")
    genre: Optional[str] = Field(
        default=None,
        description="Top raw genre tag from MusicBrainz",
    )
    classified_genre: Optional[str] = Field(
        default=None,
        description="Classified genre bucket (Rock, Pop, Metal, etc.)",
    )
    all_genres: list[str] = Field(
        default_factory=list,
        description="All genre tags with count > 1",
    )
    match_score: float = Field(default=0.0, description="Match confidence score")
    match_method: str = Field(
        default="none",
        description="Match method: 'isrc_search', 'search', 'none'",
    )
    confident_match: bool = Field(
        default=False,
        description="Whether this is a confident match",
    )


class IMVDbEnrichmentData(BaseModel):
    """IMVDb enrichment results."""

    imvdb_id: Optional[int] = Field(default=None, description="IMVDb video ID")
    imvdb_url: Optional[str] = Field(default=None, description="Full IMVDb video URL")
    year: Optional[int] = Field(default=None, description="Year from IMVDb")
    directors: Optional[str] = Field(default=None, description="Directors from IMVDb")
    featured_artists: Optional[str] = Field(
        default=None,
        description="Featured artists from IMVDb",
    )
    youtube_ids: list[str] = Field(
        default_factory=list,
        description="All YouTube video IDs from IMVDb sources",
    )
    thumbnail_url: Optional[str] = Field(
        default=None,
        description="IMVDb thumbnail URL",
    )
    match_found: bool = Field(default=False, description="Whether IMVDb match was found")


class SpotifyTrackEnrichResponse(BaseModel):
    """Unified enrichment response."""

    spotify_track_id: str = Field(description="Spotify track ID")
    musicbrainz: MusicBrainzEnrichmentData = Field(description="MusicBrainz enrichment data")
    imvdb: IMVDbEnrichmentData = Field(description="IMVDb enrichment data")

    # Resolved final values (priority: MB canonical > IMVDb > Spotify)
    title: str = Field(description="Resolved track title")
    artist: str = Field(description="Resolved artist name")
    album: Optional[str] = Field(default=None, description="Resolved album name")
    year: Optional[int] = Field(default=None, description="Resolved release year")
    label: Optional[str] = Field(default=None, description="Resolved record label")
    genre: Optional[str] = Field(default=None, description="Resolved classified genre")
    directors: Optional[str] = Field(default=None, description="Directors from IMVDb")
    featured_artists: Optional[str] = Field(
        default=None,
        description="Featured artists from IMVDb",
    )
    youtube_ids: list[str] = Field(
        default_factory=list,
        description="All YouTube video IDs from IMVDb sources",
    )
    thumbnail_url: Optional[str] = Field(
        default=None,
        description="Thumbnail URL from IMVDb",
    )

    # Status
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
    imvdb_url: Optional[str] = Field(default=None, description="Full IMVDb video URL")
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


# ==================== Artist Import Schemas ====================


class ArtistSearchRequest(BaseModel):
    """Request to search for artists on IMVDb."""

    artist_name: str = Field(
        min_length=1,
        max_length=200,
        description="Artist name to search for",
    )
    per_page: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Max results to return",
    )


class ArtistSearchResultItem(BaseModel):
    """Individual artist in search results."""

    id: int = Field(description="IMVDb entity ID")
    name: Optional[str] = Field(default=None, description="Artist name")
    slug: Optional[str] = Field(default=None, description="URL-friendly slug")
    url: Optional[str] = Field(default=None, description="IMVDb profile URL")
    image: Optional[str] = Field(default=None, description="Profile image URL")
    discogs_id: Optional[int] = Field(default=None, description="Linked Discogs ID")
    artist_video_count: int = Field(
        default=0, description="Accurate number of videos from entity details"
    )
    featured_video_count: int = Field(default=0, description="Number of videos as featured")
    sample_tracks: list[str] = Field(
        default_factory=list,
        description="First 3 track titles from artist's videos",
        max_length=3,
    )

    model_config = {"extra": "ignore"}


class ArtistSearchResponse(BaseModel):
    """Response from artist search."""

    artist_name: str = Field(description="Search query")
    total_results: int = Field(description="Total matching results")
    results: list[ArtistSearchResultItem] = Field(
        default_factory=list,
        description="Artists with video_count > 0",
    )


class ArtistVideoPreviewItem(BaseModel):
    """Single video in artist preview (for selection grid)."""

    id: int = Field(description="IMVDb video ID")
    song_title: Optional[str] = Field(default=None, description="Song title")
    year: Optional[int] = Field(default=None, description="Release year")
    url: Optional[str] = Field(default=None, description="IMVDb video URL")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail image URL")
    production_status: Optional[str] = Field(default=None, description="Production status code")
    version_name: Optional[str] = Field(default=None, description="Version name if multiple")
    already_exists: bool = Field(default=False, description="Whether video is already in library")
    existing_video_id: Optional[int] = Field(default=None, description="Existing video ID if dupe")

    model_config = {"extra": "ignore"}


class ArtistVideosPreviewResponse(BaseModel):
    """Paginated preview of artist videos for selection grid."""

    entity_id: int = Field(description="IMVDb entity ID")
    entity_name: Optional[str] = Field(default=None, description="Artist name")
    entity_slug: Optional[str] = Field(default=None, description="Artist slug")
    total_videos: int = Field(description="Total artist videos on IMVDb")
    current_page: int = Field(description="Current page number (1-indexed)")
    per_page: int = Field(description="Results per page")
    total_pages: int = Field(description="Total number of pages")
    has_more: bool = Field(description="Whether more pages are available")
    videos: list[ArtistVideoPreviewItem] = Field(
        default_factory=list,
        description="Videos for this page",
    )
    existing_count: int = Field(default=0, description="Videos already in library")
    new_count: int = Field(default=0, description="Videos not yet in library")


class ArtistVideoEnrichRequest(BaseModel):
    """Request for single IMVDb video enrichment via MusicBrainz."""

    imvdb_id: int = Field(description="IMVDb video ID")
    artist: str = Field(min_length=1, max_length=200, description="Artist name")
    track_title: str = Field(min_length=1, max_length=200, description="Song title")
    year: Optional[int] = Field(default=None, description="Release year from IMVDb")
    thumbnail_url: Optional[str] = Field(default=None, description="IMVDb thumbnail URL")


class ArtistVideoEnrichResponse(BaseModel):
    """Enrichment response for a single IMVDb video."""

    imvdb_id: int = Field(description="IMVDb video ID")

    # Source data from IMVDb video detail (fetched during enrichment)
    directors: Optional[str] = Field(default=None, description="Directors from IMVDb")
    featured_artists: Optional[str] = Field(default=None, description="Featured artists from IMVDb")
    youtube_ids: list[str] = Field(
        default_factory=list,
        description="YouTube video IDs from IMVDb sources",
    )
    imvdb_url: Optional[str] = Field(default=None, description="Full IMVDb video URL")

    # MusicBrainz enrichment
    musicbrainz: MusicBrainzEnrichmentData = Field(description="MusicBrainz enrichment data")

    # Resolved final values
    title: str = Field(description="Resolved track title")
    artist: str = Field(description="Resolved artist name")
    album: Optional[str] = Field(default=None, description="Album from MusicBrainz")
    year: Optional[int] = Field(default=None, description="Resolved release year")
    label: Optional[str] = Field(default=None, description="Record label from MusicBrainz")
    genre: Optional[str] = Field(default=None, description="Classified genre")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail URL")

    # Status
    enrichment_status: str = Field(
        default="success",
        description="Enrichment status: 'success', 'partial', or 'not_found'",
    )
    already_exists: bool = Field(default=False, description="Whether video exists in library")
    existing_video_id: Optional[int] = Field(default=None, description="Existing video ID if dupe")


class SelectedArtistVideoImport(BaseModel):
    """Single video to import from artist import workflow."""

    imvdb_id: int = Field(description="IMVDb video ID")
    metadata: dict[str, Any] = Field(
        description="Video metadata (title, artist, year, album, directors, genre, label)",
    )
    imvdb_url: Optional[str] = Field(default=None, description="Full IMVDb video URL")
    youtube_id: Optional[str] = Field(default=None, description="Selected YouTube video ID")
    youtube_url: Optional[str] = Field(default=None, description="YouTube URL")
    thumbnail_url: Optional[str] = Field(default=None, description="Thumbnail image URL")


class ArtistBatchImportRequest(BaseModel):
    """Request to import selected videos from an artist."""

    entity_id: int = Field(description="IMVDb entity ID")
    entity_name: Optional[str] = Field(default=None, description="Artist name for logging")
    videos: list[SelectedArtistVideoImport] = Field(description="Selected videos to import")
    initial_status: str = Field(
        default="discovered",
        description="Initial status for created video records",
        examples=["discovered", "imported"],
    )
    auto_download: bool = Field(
        default=False,
        description="Automatically queue download jobs for videos with YouTube IDs",
    )


class ArtistBatchImportResponse(BaseModel):
    """Response after submitting an artist batch import job."""

    job_id: str = Field(description="Background job ID")
    entity_id: int = Field(description="IMVDb entity ID")
    video_count: int = Field(description="Number of videos being imported")
    auto_download: bool = Field(description="Whether auto-download is enabled")
    status: str = Field(default="pending", description="Initial job status")
