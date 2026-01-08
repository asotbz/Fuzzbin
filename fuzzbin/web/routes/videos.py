"""Video CRUD and management endpoints."""

import mimetypes
from pathlib import Path
from typing import AsyncIterator, List, Optional, Tuple

import aiofiles
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse

import fuzzbin
from fuzzbin.auth import decode_token
from fuzzbin.common.path_security import PathSecurityError, validate_contained_path
from fuzzbin.core.db import VideoRepository
from fuzzbin.services import VideoService
from fuzzbin.services.base import NotFoundError, ServiceError, ValidationError

from ..dependencies import get_repository, get_video_service
from ..settings import get_settings
from ..schemas.common import (
    AUTH_ERROR_RESPONSES,
    COMMON_ERROR_RESPONSES,
    PageParams,
    PaginatedResponse,
    VideoStatusHistoryEntry,
)
from ..schemas.jobs import JobResponse
from ..schemas.video import (
    MusicBrainzEnrichRequest,
    MusicBrainzEnrichResponse,
    VideoCreate,
    VideoFilters,
    VideoResponse,
    VideoStatusUpdate,
    VideoUpdate,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/videos", tags=["Videos"])
# Separate router for stream endpoint (handles auth internally via query param)
stream_router = APIRouter(tags=["Videos"])

# Valid sort fields for videos
VALID_VIDEO_SORT_FIELDS = {
    "title",
    "artist",
    "album",
    "year",
    "director",
    "genre",
    "created_at",
    "updated_at",
    "status",
}


def _get_library_dir() -> Path:
    """Get configured library directory for path validation."""
    config = fuzzbin.get_config()
    if config.library_dir:
        return config.library_dir
    from fuzzbin.common.config import _get_default_library_dir

    return _get_default_library_dir()


def _validate_video_paths(
    video_file_path: Optional[str],
    nfo_file_path: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    """Validate and normalize video/NFO file paths.

    Ensures paths are contained within library_dir to prevent path traversal.

    Returns:
        Tuple of (validated_video_path, validated_nfo_path) as strings

    Raises:
        HTTPException: If paths are outside allowed directories
    """
    library_dir = _get_library_dir()
    validated_video = None
    validated_nfo = None

    if video_file_path:
        try:
            validated = validate_contained_path(video_file_path, [library_dir])
            validated_video = str(validated)
        except PathSecurityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid video file path: {e}. Path must be within library directory.",
            )

    if nfo_file_path:
        try:
            validated = validate_contained_path(nfo_file_path, [library_dir])
            validated_nfo = str(validated)
        except PathSecurityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid NFO file path: {e}. Path must be within library directory.",
            )

    return validated_video, validated_nfo


@router.get(
    "",
    response_model=PaginatedResponse[VideoResponse],
    summary="List videos",
    description="Get a paginated list of videos with optional filters and sorting.",
)
async def list_videos(
    # Pagination
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    # Sorting
    sort_by: str = Query(default="created_at", description="Sort field"),
    sort_order: str = Query(default="desc", description="Sort order: asc or desc"),
    # Filters
    title: Optional[str] = Query(default=None, description="Filter by title"),
    artist: Optional[str] = Query(default=None, description="Filter by artist"),
    album: Optional[str] = Query(default=None, description="Filter by album"),
    director: Optional[str] = Query(default=None, description="Filter by director"),
    genre: Optional[str] = Query(default=None, description="Filter by genre"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    year: Optional[int] = Query(default=None, description="Filter by year"),
    year_min: Optional[int] = Query(default=None, description="Minimum year"),
    year_max: Optional[int] = Query(default=None, description="Maximum year"),
    imvdb_video_id: Optional[str] = Query(default=None, description="Filter by IMVDb ID"),
    youtube_id: Optional[str] = Query(default=None, description="Filter by YouTube ID"),
    collection_name: Optional[str] = Query(default=None, description="Filter by collection"),
    collection_id: Optional[int] = Query(default=None, description="Filter by collection ID"),
    tag_name: Optional[str] = Query(default=None, description="Filter by tag"),
    tag_id: Optional[int] = Query(default=None, description="Filter by tag ID"),
    search: Optional[str] = Query(default=None, description="Full-text search"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted"),
    # Dependencies
    repo: VideoRepository = Depends(get_repository),
) -> PaginatedResponse[VideoResponse]:
    """List videos with filtering, sorting, and pagination."""
    page_params = PageParams(page=page, page_size=page_size)
    filters = VideoFilters(
        title=title,
        artist=artist,
        album=album,
        director=director,
        genre=genre,
        status=status,
        year=year,
        year_min=year_min,
        year_max=year_max,
        imvdb_video_id=imvdb_video_id,
        youtube_id=youtube_id,
        collection_name=collection_name,
        collection_id=collection_id,
        tag_name=tag_name,
        tag_id=tag_id,
        search=search,
        include_deleted=include_deleted,
    )

    # Build query
    query = repo.query()
    query = filters.apply_to_query(query)

    # Apply sorting
    if sort_by in VALID_VIDEO_SORT_FIELDS:
        desc = sort_order.lower() == "desc"
        query = query.order_by(sort_by, desc=desc)

    # Get total count before pagination
    total = await query.count()

    # Apply pagination
    query = query.limit(page_params.page_size).offset(page_params.offset)

    # Execute query
    rows = await query.execute()

    # Convert to response models with relationships
    items = []
    for row in rows:
        video_id = row["id"]
        artists = await repo.get_video_artists(video_id)
        collections = await repo.get_video_collections(video_id)
        tags = await repo.get_video_tags(video_id)
        items.append(
            VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)
        )

    return PaginatedResponse.create(items, total, page_params)


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Get video by ID",
    description="Get detailed information about a specific video.",
)
async def get_video(
    video_id: int,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    repo: VideoRepository = Depends(get_repository),
) -> VideoResponse:
    """Get a video by ID with relationships."""
    row = await repo.get_video_by_id(video_id, include_deleted=include_deleted)
    artists = await repo.get_video_artists(video_id)
    collections = await repo.get_video_collections(video_id)
    tags = await repo.get_video_tags(video_id)
    return VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)


@router.post(
    "",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create video",
    description="Create a new video record.",
)
async def create_video(
    video: VideoCreate,
    repo: VideoRepository = Depends(get_repository),
) -> VideoResponse:
    """Create a new video."""
    # Validate file paths to prevent path traversal
    validated_video_path, validated_nfo_path = _validate_video_paths(
        video.video_file_path,
        video.nfo_file_path,
    )

    video_id = await repo.create_video(**video.to_repo_kwargs())

    # If file paths were provided, update them separately (with validated paths)
    if validated_video_path or validated_nfo_path:
        await repo.update_video(
            video_id,
            video_file_path=validated_video_path,
            nfo_file_path=validated_nfo_path,
        )

    row = await repo.get_video_by_id(video_id)
    return VideoResponse.from_db_row(row)


@router.patch(
    "/{video_id}",
    response_model=VideoResponse,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Update video",
    description="Update video metadata. Only provided fields are updated.",
)
async def update_video(
    video_id: int,
    video: VideoUpdate,
    repo: VideoRepository = Depends(get_repository),
) -> VideoResponse:
    """Update a video's metadata."""
    from fuzzbin.tasks.models import Job, JobType, JobPriority
    from fuzzbin.tasks.queue import get_job_queue

    # Get current video to check for changes that affect file paths
    current_video = await repo.get_video_by_id(video_id)

    # Validate file paths if provided
    if video.video_file_path is not None or video.nfo_file_path is not None:
        validated_video_path, validated_nfo_path = _validate_video_paths(
            video.video_file_path,
            video.nfo_file_path,
        )
        # Update the video object with validated paths
        if video.video_file_path is not None:
            video.video_file_path = validated_video_path
        if video.nfo_file_path is not None:
            video.nfo_file_path = validated_nfo_path

    # Update with provided fields
    updates = video.to_repo_kwargs()
    if updates:
        await repo.update_video(video_id, **updates)

    # Check if artist or title changed - queue file reorganization if so
    # Only reorganize if there's an existing video file
    if current_video.get("video_file_path"):
        artist_changed = "artist" in updates and updates["artist"] != current_video.get("artist")
        title_changed = "title" in updates and updates["title"] != current_video.get("title")

        if artist_changed or title_changed:
            queue = get_job_queue()
            job = Job(
                type=JobType.FILE_ORGANIZE,
                metadata={
                    "video_id": video_id,
                    "video_ids": [video_id],
                    "trigger": "metadata_update",
                },
                priority=JobPriority.NORMAL,
            )
            try:
                await queue.submit(job)
                logger.info(
                    "file_organize_queued_for_metadata_change",
                    video_id=video_id,
                    job_id=job.id,
                    artist_changed=artist_changed,
                    title_changed=title_changed,
                )
            except Exception as e:
                # Don't fail the update if we can't queue the organize job
                logger.warning(
                    "file_organize_queue_failed",
                    video_id=video_id,
                    error=str(e),
                )

    # Fetch updated video with relationships
    row = await repo.get_video_by_id(video_id)
    artists = await repo.get_video_artists(video_id)
    collections = await repo.get_video_collections(video_id)
    tags = await repo.get_video_tags(video_id)
    return VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)


@router.patch(
    "/{video_id}/status",
    response_model=VideoResponse,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Update video status",
    description="Update the status of a video with optional reason and metadata.",
)
async def update_video_status(
    video_id: int,
    status_update: VideoStatusUpdate,
    repo: VideoRepository = Depends(get_repository),
) -> VideoResponse:
    """Update a video's status with tracking."""
    # Verify video exists
    await repo.get_video_by_id(video_id)

    # Update status
    await repo.update_status(
        video_id=video_id,
        new_status=status_update.status,
        reason=status_update.reason,
        changed_by=status_update.changed_by or "api",
        metadata=status_update.metadata,
    )

    # Fetch updated video
    row = await repo.get_video_by_id(video_id)
    artists = await repo.get_video_artists(video_id)
    collections = await repo.get_video_collections(video_id)
    tags = await repo.get_video_tags(video_id)
    return VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)


@router.delete(
    "/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Soft delete video",
    description="Soft delete a video (can be restored later).",
)
async def delete_video(
    video_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Soft delete a video."""
    # Verify video exists
    await repo.get_video_by_id(video_id)
    await repo.delete_video(video_id)


@router.post(
    "/{video_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Add tag to video",
    description="Add a tag to a video.",
)
async def add_video_tag(
    video_id: int,
    tag_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Add a tag to a video."""
    # Verify video and tag exist
    await repo.get_video_by_id(video_id)
    await repo.get_tag_by_id(tag_id)
    await repo.add_video_tag(video_id, tag_id)


@router.delete(
    "/{video_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Remove tag from video",
    description="Remove a tag from a video.",
)
async def remove_video_tag(
    video_id: int,
    tag_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Remove a tag from a video."""
    # Verify video and tag exist
    await repo.get_video_by_id(video_id)
    await repo.get_tag_by_id(tag_id)
    await repo.remove_video_tag(video_id, tag_id)


@router.post(
    "/{video_id}/restore",
    response_model=VideoResponse,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Restore video",
    description="Restore a soft-deleted video.",
)
async def restore_video(
    video_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> VideoResponse:
    """Restore a soft-deleted video."""
    # Verify video exists (including deleted)
    await repo.get_video_by_id(video_id, include_deleted=True)
    await repo.restore_video(video_id)

    row = await repo.get_video_by_id(video_id)
    artists = await repo.get_video_artists(video_id)
    collections = await repo.get_video_collections(video_id)
    tags = await repo.get_video_tags(video_id)
    return VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)


@router.post(
    "/{video_id}/download",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**COMMON_ERROR_RESPONSES, **AUTH_ERROR_RESPONSES},
    summary="Queue video download",
    description="Queue download job for a video with a YouTube ID. Downloads to temp, organizes to configured path, and generates NFO.",
)
async def download_video(
    video_id: int,
    repository: VideoRepository = Depends(get_repository),
) -> JobResponse:
    """Queue download job for a video with a YouTube ID.

    Downloads video to temporary location, then organizes to library
    structure using configured path pattern, and generates NFO file.
    """
    from fuzzbin.tasks.models import Job, JobType, JobPriority
    from fuzzbin.tasks.queue import get_job_queue

    # Get video to verify it exists and has youtube_id
    video = await repository.get_video_by_id(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Video {video_id} not found"
        )

    youtube_id = video.get("youtube_id")
    if not youtube_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Video does not have a YouTube ID"
        )

    # Queue IMPORT_DOWNLOAD job (will auto-queue organize and NFO jobs)
    queue = get_job_queue()
    job = Job(
        type=JobType.IMPORT_DOWNLOAD,
        metadata={
            "video_id": video_id,
            "youtube_id": youtube_id,
        },
        priority=JobPriority.HIGH,
    )
    await queue.submit(job)

    return JobResponse.model_validate(job)


@router.post(
    "/{video_id}/enrich/musicbrainz",
    response_model=MusicBrainzEnrichResponse,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Enrich video with MusicBrainz",
    description="Enrich video metadata from MusicBrainz using ISRC (preferred) or title/artist search. Returns enrichment result for user preview/approval.",
)
async def enrich_video_musicbrainz(
    video_id: int,
    request: MusicBrainzEnrichRequest,
    repo: VideoRepository = Depends(get_repository),
) -> MusicBrainzEnrichResponse:
    """Enrich video metadata from MusicBrainz.

    Uses ISRC if provided (most reliable), otherwise falls back to title/artist search.
    Returns enrichment result with match confidence for user approval.
    Does not automatically update the video record - user must apply changes via PATCH endpoint.
    """
    from fuzzbin.services.musicbrainz_enrichment import MusicBrainzEnrichmentService

    # Verify video exists and get current data
    video = await repo.get_video_by_id(video_id)

    # Use provided values or fall back to video's existing values
    isrc = request.isrc or video.get("isrc")
    title = request.title or video.get("title")
    artist = request.artist or video.get("artist")

    # Require at least ISRC or title+artist
    if not isrc and not (title and artist):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either ISRC or both title and artist",
        )

    # Create enrichment service
    config = fuzzbin.get_config()
    api_config = config.apis.get("musicbrainz") if config.apis else None
    enrichment_service = MusicBrainzEnrichmentService(
        config=api_config,
        config_dir=config.config_dir,
    )

    # Perform enrichment
    logger.info(
        "musicbrainz_enrichment_requested",
        video_id=video_id,
        has_isrc=bool(isrc),
        title=title,
        artist=artist,
    )

    result = await enrichment_service.enrich(
        isrc=isrc,
        artist=artist,
        title=title,
    )

    logger.info(
        "musicbrainz_enrichment_complete",
        video_id=video_id,
        match_method=result.match_method,
        match_score=result.match_score,
        confident_match=result.confident_match,
    )

    # Convert result to response schema
    return MusicBrainzEnrichResponse(
        recording_mbid=result.recording_mbid,
        release_mbid=result.release_mbid,
        album=result.album,
        year=result.year,
        genre=result.genre,
        label=result.label,
        canonical_title=result.canonical_title,
        canonical_artist=result.canonical_artist,
        classified_genre=result.classified_genre,
        match_score=result.match_score,
        match_method=result.match_method,
        confident_match=result.confident_match,
        all_genres=result.all_genres,
        release_type=result.release_type,
    )


@router.get(
    "/{video_id}/jobs",
    response_model=List[JobResponse],
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Get jobs for video",
    description="Get active and pending jobs associated with a specific video. "
    "Returns jobs where metadata.video_id matches the requested video.",
)
async def get_video_jobs(
    video_id: int,
    include_completed: bool = Query(
        default=False, description="Include completed/failed jobs (default: only active)"
    ),
    repository: VideoRepository = Depends(get_repository),
) -> List[JobResponse]:
    """Get jobs associated with a video.

    Returns jobs where metadata.video_id matches the requested video ID.
    By default, only returns active jobs (pending, waiting, running).
    Set include_completed=true to also include terminal jobs.
    """
    from fuzzbin.tasks.queue import get_job_queue
    from fuzzbin.tasks.models import JobStatus

    # Verify video exists
    await repository.get_video_by_id(video_id)

    queue = get_job_queue()
    all_jobs = await queue.list_jobs(limit=1000)

    # Filter to jobs for this video
    matching_jobs = []
    active_statuses = {JobStatus.PENDING, JobStatus.WAITING, JobStatus.RUNNING}

    for job in all_jobs:
        job_video_id = job.metadata.get("video_id")
        if job_video_id != video_id:
            continue

        # Filter by status if not including completed
        if not include_completed and job.status not in active_statuses:
            continue

        matching_jobs.append(job)

    return [JobResponse.model_validate(job) for job in matching_jobs]


@router.delete(
    "/{video_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Permanently delete video",
    description="Permanently delete a video. This cannot be undone.",
)
async def hard_delete_video(
    video_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Permanently delete a video."""
    # Verify video exists (including deleted)
    await repo.get_video_by_id(video_id, include_deleted=True)
    await repo.hard_delete_video(video_id)


@router.get(
    "/{video_id}/status-history",
    response_model=List[VideoStatusHistoryEntry],
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Get status history",
    description="Get the status change history for a video.",
)
async def get_video_status_history(
    video_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> List[VideoStatusHistoryEntry]:
    """Get a video's status change history."""
    # Verify video exists
    await repo.get_video_by_id(video_id, include_deleted=True)
    history = await repo.get_status_history(video_id)
    return [
        VideoStatusHistoryEntry(
            id=entry["id"],
            video_id=entry["video_id"],
            old_status=entry.get("old_status"),
            new_status=entry["new_status"],
            reason=entry.get("reason"),
            changed_at=entry["changed_at"],
        )
        for entry in history
    ]


# Constants for streaming
STREAM_CHUNK_SIZE = 1024 * 1024  # 1MB chunks


def _parse_range_header(range_header: str, file_size: int) -> Tuple[int, int]:
    """
    Parse HTTP Range header and return start and end byte positions.

    Args:
        range_header: The Range header value (e.g., "bytes=0-1023")
        file_size: Total file size in bytes

    Returns:
        Tuple of (start_byte, end_byte) inclusive

    Raises:
        HTTPException: If range is invalid or unsatisfiable
    """
    if not range_header.startswith("bytes="):
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail="Invalid range header format",
        )

    range_spec = range_header[6:]  # Remove "bytes=" prefix

    # Handle multiple ranges - we only support single range
    if "," in range_spec:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail="Multiple ranges not supported",
        )

    try:
        if range_spec.startswith("-"):
            # Suffix range: -500 means last 500 bytes
            suffix_length = int(range_spec[1:])
            start = max(0, file_size - suffix_length)
            end = file_size - 1
        elif range_spec.endswith("-"):
            # Open-ended range: 500- means from byte 500 to end
            start = int(range_spec[:-1])
            end = file_size - 1
        else:
            # Explicit range: 0-499
            parts = range_spec.split("-")
            start = int(parts[0])
            end = int(parts[1]) if parts[1] else file_size - 1
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail="Invalid range values",
        )

    # Validate range
    if start < 0 or end >= file_size or start > end:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail=f"Range not satisfiable. File size: {file_size}",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    return start, end


def _get_content_type(file_path: Path) -> str:
    """Get MIME type for video file based on extension."""
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


async def _stream_file_range(
    file_path: Path,
    start: int,
    end: int,
    chunk_size: int = STREAM_CHUNK_SIZE,
) -> AsyncIterator[bytes]:
    """
    Async generator that streams a byte range from a file.

    Args:
        file_path: Path to the file
        start: Start byte position (inclusive)
        end: End byte position (inclusive)
        chunk_size: Size of chunks to read

    Yields:
        Chunks of file data
    """
    async with aiofiles.open(file_path, "rb") as f:
        await f.seek(start)
        remaining = end - start + 1

        while remaining > 0:
            read_size = min(chunk_size, remaining)
            data = await f.read(read_size)
            if not data:
                break
            remaining -= len(data)
            yield data


@router.get(
    "/{video_id}/thumbnail",
    summary="Get video thumbnail",
    description="Get or generate a thumbnail for a video.",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {
            "description": "Thumbnail image",
            "content": {"image/jpeg": {}},
        },
        404: {"description": "Video not found or no file associated"},
        500: {"description": "Thumbnail generation failed"},
    },
)
async def get_video_thumbnail(
    video_id: int,
    regenerate: bool = Query(default=False, description="Force thumbnail regeneration"),
    timestamp: Optional[float] = Query(
        default=None, description="Timestamp in seconds to extract frame from"
    ),
    video_service: VideoService = Depends(get_video_service),
) -> StreamingResponse:
    """
    Get or generate a thumbnail for a video.

    Returns a JPEG thumbnail extracted from the video file. Thumbnails
    are cached in the thumbnail cache directory for subsequent requests.

    Requires authentication.
    """
    try:
        thumb_path = await video_service.get_thumbnail(
            video_id=video_id,
            timestamp=timestamp,
            regenerate=regenerate,
        )

        # Stream the thumbnail
        thumb_size = thumb_path.stat().st_size

        return StreamingResponse(
            _stream_file_range(thumb_path, 0, thumb_size - 1),
            status_code=status.HTTP_200_OK,
            media_type="image/jpeg",
            headers={
                "Content-Length": str(thumb_size),
                "Cache-Control": "private, max-age=86400, stale-while-revalidate=3600",
            },
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e.message),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.message),
        )
    except ServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e.message),
        )


@router.post(
    "/{video_id}/refresh",
    summary="Refresh video properties and thumbnail",
    description="Re-analyze video file with ffprobe and regenerate thumbnail.",
    responses={
        **AUTH_ERROR_RESPONSES,
        200: {
            "description": "Video properties refreshed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "video_id": 123,
                        "media_info": {
                            "duration": 240.5,
                            "width": 1920,
                            "height": 1080,
                            "video_codec": "h264",
                            "audio_codec": "aac",
                        },
                        "thumbnail_path": "/config/.thumbnails/123.jpg",
                        "thumbnail_timestamp": 1704067200,
                    }
                }
            },
        },
        404: {"description": "Video not found or no file associated"},
        500: {"description": "Refresh failed"},
    },
)
async def refresh_video(
    video_id: int,
    regenerate_thumbnail: bool = Query(
        default=True,
        description="Regenerate thumbnail from video file using ffmpeg",
    ),
    video_service: VideoService = Depends(get_video_service),
):
    """
    Refresh video file properties and optionally regenerate thumbnail.

    Runs ffprobe to re-analyze the video file and update technical metadata
    (duration, resolution, codecs). When regenerate_thumbnail is True,
    extracts a new thumbnail frame at 20% of video duration.

    Emits a video_updated WebSocket event with thumbnail_timestamp for
    client-side cache invalidation.

    Requires authentication.
    """
    from fuzzbin.core.event_bus import get_event_bus

    try:
        result = await video_service.refresh_video_properties(
            video_id=video_id,
            regenerate_thumbnail=regenerate_thumbnail,
        )

        # Emit video_updated event for real-time UI updates
        fields_changed = ["file_properties"]
        if regenerate_thumbnail and result.get("thumbnail_path"):
            fields_changed.append("thumbnail")

        try:
            event_bus = get_event_bus()
            await event_bus.emit_video_updated(
                video_id=video_id,
                fields_changed=fields_changed,
                thumbnail_timestamp=result.get("thumbnail_timestamp"),
            )
        except RuntimeError:
            # Event bus not initialized (e.g., in tests)
            pass

        return {
            "video_id": video_id,
            "media_info": result.get("media_info", {}),
            "thumbnail_path": result.get("thumbnail_path"),
            "thumbnail_timestamp": result.get("thumbnail_timestamp"),
        }

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e.message),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e.message),
        )
    except ServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e.message),
        )


@stream_router.get(
    "/videos/{video_id}/stream",
    summary="Stream video file",
    description="Stream video file with HTTP Range support for seeking.",
    responses={
        200: {
            "description": "Full video file (no Range header)",
            "content": {"video/*": {}},
        },
        206: {
            "description": "Partial content (Range header provided)",
            "content": {"video/*": {}},
        },
        404: {"description": "Video not found or no file associated"},
        416: {"description": "Requested range not satisfiable"},
    },
)
async def stream_video(
    video_id: int,
    range: Optional[str] = Header(default=None, alias="Range"),
    token: Optional[str] = Query(
        default=None,
        description="JWT token for authentication (alternative to Authorization header)",
    ),
    repo: VideoRepository = Depends(get_repository),
) -> StreamingResponse:
    """
    Stream video file with HTTP Range support.

    Supports:
    - Full file download (no Range header)
    - Byte range requests for seeking (Range: bytes=start-end)
    - Suffix ranges (Range: bytes=-500 for last 500 bytes)
    - Open-ended ranges (Range: bytes=500- for byte 500 to end)

    Authentication:
    - Validates JWT token from query parameter (for <video> element compatibility)
    - Only required when API authentication is enabled
    """
    # Validate query parameter token if authentication is enabled
    settings = get_settings()
    if settings.auth_enabled:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Decode and validate token
        payload = decode_token(
            token=token,
            secret_key=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
            expected_type="access",
        )

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Get video and verify it has a file
    video = await repo.get_video_by_id(video_id)
    file_path_str = video.get("video_file_path")

    if not file_path_str:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No video file associated with this video",
        )

    # Validate the stored path is within library_dir (defense in depth)
    library_dir = _get_library_dir()
    try:
        file_path = validate_contained_path(file_path_str, [library_dir], must_exist=False)
    except PathSecurityError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Video file path is outside allowed directories",
        )

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file not found on disk",
        )

    file_size = file_path.stat().st_size
    content_type = _get_content_type(file_path)

    # Handle Range header
    if range:
        start, end = _parse_range_header(range, file_size)
        content_length = end - start + 1

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
        }

        return StreamingResponse(
            _stream_file_range(file_path, start, end),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type=content_type,
            headers=headers,
        )

    # No Range header - return full file
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(file_size),
    }

    return StreamingResponse(
        _stream_file_range(file_path, 0, file_size - 1),
        status_code=status.HTTP_200_OK,
        media_type=content_type,
        headers=headers,
    )


@router.post(
    "/backfill-imvdb-urls",
    status_code=status.HTTP_200_OK,
    responses={**COMMON_ERROR_RESPONSES, **AUTH_ERROR_RESPONSES},
)
async def backfill_imvdb_urls(
    limit: Optional[int] = Query(None, description="Limit number of videos to process"),
    video_service: VideoService = Depends(get_video_service),
) -> dict:
    """
    Backfill missing IMVDb URLs for videos that have imvdb_video_id.

    This endpoint is useful for fixing videos that were imported with
    imvdb_video_id but missing imvdb_url (e.g., due to bugs or data migration).

    Args:
        limit: Optional limit on number of videos to process
        video_service: Injected video service

    Returns:
        Dict with counts: total_found, updated, failed
    """
    try:
        # Get IMVDb client from dependencies
        from ..dependencies import get_imvdb_client

        imvdb_client = await get_imvdb_client()

        result = await video_service.backfill_imvdb_urls(
            imvdb_client=imvdb_client,
            limit=limit,
        )

        return result

    except ServiceError as e:
        logger.error("backfill_imvdb_urls_service_error", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error("backfill_imvdb_urls_unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to backfill IMVDb URLs",
        )
