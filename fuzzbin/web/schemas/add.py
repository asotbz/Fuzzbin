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
