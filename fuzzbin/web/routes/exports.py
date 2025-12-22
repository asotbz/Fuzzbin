"""Export workflow endpoints (Phase 7).

Provides endpoints for:
- NFO file regeneration (bulk export)
- Playlist export (M3U, CSV, JSON)
"""

import csv
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, List, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

import fuzzbin
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.core.db import VideoRepository
from fuzzbin.core.db.exporter import NFOExporter

from ..dependencies import get_repository, require_auth
from ..schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES
from ..schemas.video import VideoFilters

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/exports", tags=["Exports"])


# ==================== Request/Response Schemas ====================


class NFOExportRequest(BaseModel):
    """Request for NFO export."""

    video_ids: Optional[List[int]] = Field(
        default=None, description="Specific video IDs to export (exports all if not specified)"
    )
    include_deleted: bool = Field(default=False, description="Include soft-deleted videos")
    overwrite_existing: bool = Field(default=False, description="Overwrite existing NFO files")


class NFOExportResult(BaseModel):
    """Result of NFO export operation."""

    total: int = Field(description="Total videos processed")
    exported_count: int = Field(description="Successfully exported")
    skipped_count: int = Field(description="Skipped (no file path or exists)")
    failed_count: int = Field(description="Failed to export")
    library_dir: str = Field(description="Library directory where NFO files are written")
    manifest_path: Optional[str] = Field(description="Path to manifest file")


class PlaylistExportRequest(BaseModel):
    """Request for playlist export."""

    name: str = Field(..., min_length=1, max_length=200, description="Playlist name")
    output_path: str = Field(
        ...,
        min_length=1,
        description="Full path where playlist file will be written (including filename)",
    )
    video_ids: Optional[List[int]] = Field(
        default=None, description="Specific video IDs (exports all if not specified)"
    )
    format: Literal["m3u", "csv", "json"] = Field(default="m3u", description="Export format")
    include_deleted: bool = Field(default=False, description="Include soft-deleted videos")


class PlaylistExportResult(BaseModel):
    """Result of playlist export."""

    name: str = Field(description="Playlist name")
    format: str = Field(description="Export format")
    total_tracks: int = Field(description="Number of tracks in playlist")
    file_path: str = Field(description="Path to exported file")


# ==================== Helper Functions ====================


async def _get_library_dir() -> Path:
    """Get configured library directory for NFO file output."""
    config = fuzzbin.get_config()
    if config.library_dir:
        return config.library_dir
    # Fallback to default
    from fuzzbin.common.config import _get_default_library_dir

    return _get_default_library_dir()


async def _get_config_dir() -> Path:
    """Get configured config directory for manifest files."""
    config = fuzzbin.get_config()
    if config.config_dir:
        return config.config_dir
    # Fallback to default
    from fuzzbin.common.config import _get_default_config_dir

    return _get_default_config_dir()


# ==================== NFO Export ====================


@router.post(
    "/nfo",
    response_model=NFOExportResult,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Export NFO files",
    description="Regenerate NFO files for videos. NFO files are written alongside video files in the library.",
)
async def export_nfo_files(
    request: NFOExportRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> NFOExportResult:
    """
    Export/regenerate NFO files for videos.

    This creates or updates NFO metadata files based on current database state.
    NFO files are written alongside video files in the library directory:
    - <basename>.nfo: One per video file, matching the video's base name
    - artist.nfo: One per artist directory (created automatically)
    """
    library_dir = await _get_library_dir()
    config_dir = await _get_config_dir()
    exporter = NFOExporter(repo)

    # Get videos to export
    if request.video_ids:
        videos = []
        for vid in request.video_ids:
            try:
                video = await repo.get_video_by_id(vid, include_deleted=request.include_deleted)
                videos.append(video)
            except Exception:
                pass  # Skip not found
    else:
        # Get all videos
        query = repo.query()
        if request.include_deleted:
            query = query.include_deleted()
        videos = await query.execute()

    exported_count = 0
    skipped_count = 0
    failed_count = 0
    manifest_entries = []

    for video in videos:
        video_id = video["id"]
        nfo_path_str = video.get("nfo_file_path")

        if not nfo_path_str:
            # No NFO path, try to generate one from video path
            video_path = video.get("video_file_path")
            if video_path:
                nfo_path = Path(video_path).with_suffix(".nfo")
            else:
                skipped_count += 1
                continue
        else:
            nfo_path = Path(nfo_path_str)

        # Check if exists and skip if not overwriting
        if nfo_path.exists() and not request.overwrite_existing:
            skipped_count += 1
            continue

        try:
            exported_path = await exporter.export_video_to_nfo(video_id, nfo_path)
            exported_count += 1
            manifest_entries.append(
                {
                    "video_id": video_id,
                    "title": video.get("title"),
                    "nfo_path": str(exported_path),
                }
            )
        except Exception as e:
            failed_count += 1
            logger.error(
                "nfo_export_failed",
                video_id=video_id,
                error=str(e),
            )

    # Write manifest to config_dir
    manifest_path = None
    if manifest_entries:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        manifest_file = config_dir / f"nfo_export_{timestamp}.json"
        with open(manifest_file, "w") as f:
            json.dump(
                {
                    "exported_at": datetime.now().isoformat(),
                    "exported_by": current_user.username if current_user else "anonymous",
                    "total": len(manifest_entries),
                    "files": manifest_entries,
                },
                f,
                indent=2,
            )
        manifest_path = str(manifest_file)

    logger.info(
        "nfo_export_completed",
        total=len(videos),
        exported=exported_count,
        skipped=skipped_count,
        failed=failed_count,
        user=current_user.username if current_user else "anonymous",
    )

    return NFOExportResult(
        total=len(videos),
        exported_count=exported_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        library_dir=str(library_dir),
        manifest_path=manifest_path,
    )


# ==================== Playlist Export ====================


@router.post(
    "/playlist",
    response_model=PlaylistExportResult,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Export playlist",
    description="Export videos as a playlist in M3U, CSV, or JSON format.",
)
async def export_playlist(
    request: PlaylistExportRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> PlaylistExportResult:
    """
    Export videos as a playlist file.

    Supported formats:
    - m3u: Extended M3U playlist (for media players)
    - csv: CSV with title, artist, album, path columns
    - json: Full video metadata as JSON array

    The output_path must be provided by the user specifying where to write the file.
    """
    # Validate and prepare output path
    file_path = Path(request.output_path)

    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Get videos
    if request.video_ids:
        videos = []
        for vid in request.video_ids:
            try:
                video = await repo.get_video_by_id(vid, include_deleted=request.include_deleted)
                videos.append(video)
            except Exception:
                pass
    else:
        query = repo.query()
        if request.include_deleted:
            query = query.include_deleted()
        videos = await query.execute()

    # Filter to videos with file paths for M3U
    if request.format == "m3u":
        videos = [v for v in videos if v.get("video_file_path")]

    # Generate content based on format
    if request.format == "m3u":
        content = _generate_m3u(videos, request.name)
    elif request.format == "csv":
        content = _generate_csv(videos)
    else:  # json
        content = _generate_json(videos, request.name)

    # Write file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    logger.info(
        "playlist_exported",
        name=request.name,
        format=request.format,
        total_tracks=len(videos),
        file_path=str(file_path),
        user=current_user.username if current_user else "anonymous",
    )

    return PlaylistExportResult(
        name=request.name,
        format=request.format,
        total_tracks=len(videos),
        file_path=str(file_path),
    )


def _generate_m3u(videos: List[dict], playlist_name: str) -> str:
    """Generate M3U playlist content."""
    lines = ["#EXTM3U", f"#PLAYLIST:{playlist_name}", ""]

    for video in videos:
        file_path = video.get("video_file_path")
        if not file_path:
            continue

        title = video.get("title", "Unknown")
        artist = video.get("artist", "Unknown")
        duration = video.get("duration")

        # Duration in seconds (default -1 for unknown)
        dur = int(duration) if duration else -1

        lines.append(f"#EXTINF:{dur},{artist} - {title}")
        lines.append(file_path)
        lines.append("")

    return "\n".join(lines)


def _generate_csv(videos: List[dict]) -> str:
    """Generate CSV content."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "id",
            "title",
            "artist",
            "album",
            "year",
            "genre",
            "director",
            "studio",
            "video_file_path",
            "status",
        ]
    )

    # Rows
    for video in videos:
        writer.writerow(
            [
                video.get("id"),
                video.get("title"),
                video.get("artist"),
                video.get("album"),
                video.get("year"),
                video.get("genre"),
                video.get("director"),
                video.get("studio"),
                video.get("video_file_path"),
                video.get("status"),
            ]
        )

    return output.getvalue()


def _generate_json(videos: List[dict], playlist_name: str) -> str:
    """Generate JSON content."""
    # Clean up sqlite Row objects to regular dicts
    clean_videos = []
    for v in videos:
        clean = {
            "id": v.get("id"),
            "title": v.get("title"),
            "artist": v.get("artist"),
            "album": v.get("album"),
            "year": v.get("year"),
            "genre": v.get("genre"),
            "director": v.get("director"),
            "studio": v.get("studio"),
            "video_file_path": v.get("video_file_path"),
            "status": v.get("status"),
            "imvdb_video_id": v.get("imvdb_video_id"),
            "youtube_id": v.get("youtube_id"),
        }
        clean_videos.append(clean)

    return json.dumps(
        {
            "playlist_name": playlist_name,
            "exported_at": datetime.now().isoformat(),
            "total_tracks": len(clean_videos),
            "videos": clean_videos,
        },
        indent=2,
        ensure_ascii=False,
    )
