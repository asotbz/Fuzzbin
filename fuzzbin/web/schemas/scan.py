"""Schemas for library scanning and import operations.

These schemas support the library scan workflow which can:
- Option A: Full import - import videos as they exist with all metadata
- Option B: Discovery only - create minimal records for follow-on workflows
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ImportMode(str, Enum):
    """Import mode for scanned videos.

    Determines how much data is imported and what status videos receive.
    """

    FULL = "full"
    """Full import: Import all metadata from NFO files. Videos get 'imported' status."""

    DISCOVERY = "discovery"
    """Discovery only: Import only title and artist. Videos get 'discovered' status
    for follow-on metadata enrichment and organization workflows."""


class ScanRequest(BaseModel):
    """Request to scan a directory for music videos.

    Supports two modes:
    - `full`: Import all metadata from NFO files, set status to 'imported'
    - `discovery`: Only capture title/artist, set status to 'discovered'

    Example:
        >>> # Full import
        >>> request = ScanRequest(
        ...     directory="/media/music_videos",
        ...     mode=ImportMode.FULL,
        ...     recursive=True
        ... )

        >>> # Discovery for workflow
        >>> request = ScanRequest(
        ...     directory="/media/unsorted",
        ...     mode=ImportMode.DISCOVERY,
        ...     skip_existing=True
        ... )
    """

    directory: str = Field(
        ...,
        description="Path to directory to scan for music videos/NFO files",
        examples=["/media/music_videos", "/home/user/downloads/videos"],
    )
    mode: ImportMode = Field(
        default=ImportMode.FULL,
        description="Import mode: 'full' imports all metadata, 'discovery' only title/artist",
    )
    recursive: bool = Field(default=True, description="Scan subdirectories recursively")
    skip_existing: bool = Field(
        default=True, description="Skip videos that already exist in the database (by title+artist)"
    )
    update_file_paths: bool = Field(
        default=True, description="Store NFO file paths in database records"
    )


class ScanPreviewItem(BaseModel):
    """Preview of a single video to be imported."""

    nfo_path: str = Field(description="Path to the NFO file")
    title: str = Field(description="Video title from NFO")
    artist: str = Field(description="Primary artist from NFO")
    album: Optional[str] = Field(default=None, description="Album name")
    year: Optional[int] = Field(default=None, description="Release year")
    already_exists: bool = Field(
        default=False, description="Whether this video already exists in the database"
    )


class ScanPreviewResponse(BaseModel):
    """Response from scan preview (dry run).

    Shows what would be imported without making any changes.
    """

    directory: str = Field(description="Directory that was scanned")
    total_nfo_files: int = Field(description="Total NFO files found")
    musicvideo_nfos: int = Field(description="Music video NFO files (vs artist NFOs)")
    would_import: int = Field(description="Videos that would be imported")
    would_skip: int = Field(description="Videos that would be skipped (already exist)")
    items: List[ScanPreviewItem] = Field(
        default_factory=list, description="Preview of individual videos (limited to first 100)"
    )
    mode: ImportMode = Field(description="Import mode that would be used")


class ScanJobResponse(BaseModel):
    """Response when submitting a scan job.

    The scan runs as a background job. Use the job_id to track progress
    via GET /jobs/{job_id} or WebSocket /ws/jobs/{job_id}.
    """

    job_id: str = Field(description="Background job ID for tracking")
    message: str = Field(description="Status message")
    directory: str = Field(description="Directory being scanned")
    mode: ImportMode = Field(description="Import mode being used")
    initial_status: str = Field(description="Status that will be assigned to new videos")


class ScanResultItem(BaseModel):
    """Result for a single video import attempt."""

    nfo_path: str = Field(description="Path to the NFO file")
    title: str = Field(description="Video title")
    artist: str = Field(description="Primary artist")
    status: str = Field(description="Result: 'imported', 'skipped', or 'failed'")
    video_id: Optional[int] = Field(default=None, description="Database ID if imported")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class ScanResultResponse(BaseModel):
    """Final result of a completed scan job.

    Retrieved via GET /jobs/{job_id} when job completes.
    """

    directory: str = Field(description="Directory that was scanned")
    mode: ImportMode = Field(description="Import mode used")
    total_files: int = Field(description="Total NFO files processed")
    imported_count: int = Field(description="Videos successfully imported")
    skipped_count: int = Field(description="Videos skipped (already exist)")
    failed_count: int = Field(description="Videos that failed to import")
    duration_seconds: float = Field(description="Time taken for scan")
    failed_files: List[Dict[str, Any]] = Field(
        default_factory=list, description="Details of failed imports"
    )
