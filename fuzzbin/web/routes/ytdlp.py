"""yt-dlp API endpoints for YouTube search, metadata, and download.

Provides REST API access to yt-dlp functionality:
- Search YouTube for music videos
- Get metadata for individual videos
- Download videos with progress tracking via WebSocket
- Cancel in-progress downloads
"""

from pathlib import Path
from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

import fuzzbin
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.common.config import YTDLPConfig
from fuzzbin.common.path_security import PathSecurityError, validate_contained_path
from fuzzbin.core.exceptions import YTDLPError, YTDLPExecutionError, YTDLPNotFoundError
from fuzzbin.tasks import Job, JobType, get_job_queue

from ..dependencies import require_auth
from ..schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES
from ..schemas.jobs import JobResponse
from ..schemas.ytdlp import (
    YTDLPDownloadRequest,
    YTDLPSearchRequest,
    YTDLPSearchResponse,
    YTDLPVideoInfo,
    YTDLPVideoInfoResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/ytdlp", tags=["yt-dlp"])


def _get_library_dir() -> Path:
    """Get configured library directory for path validation."""
    config = fuzzbin.get_config()
    if config.library_dir:
        return config.library_dir
    from fuzzbin.common.config import _get_default_library_dir

    return _get_default_library_dir()


def _validate_download_path(output_path: str) -> Path:
    """Validate download path is within library_dir.

    Args:
        output_path: Relative or absolute path for download destination

    Returns:
        Validated absolute Path within library directory

    Raises:
        HTTPException: If path is outside library directory
    """
    library_dir = _get_library_dir()

    # If relative path, join with library_dir
    if not Path(output_path).is_absolute():
        full_path = library_dir / output_path
    else:
        full_path = Path(output_path)

    try:
        validated = validate_contained_path(str(full_path), [library_dir])
        return validated
    except PathSecurityError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid output path: {e}. Path must be within library directory.",
        )


def _get_ytdlp_config() -> YTDLPConfig:
    """Get yt-dlp configuration from global config."""
    config = fuzzbin.get_config()
    return config.ytdlp


def _convert_to_video_info(result) -> YTDLPVideoInfo:
    """Convert YTDLPSearchResult to YTDLPVideoInfo schema."""
    return YTDLPVideoInfo(
        id=result.id,
        title=result.title,
        url=result.url,
        channel=result.channel,
        channel_follower_count=result.channel_follower_count,
        view_count=result.view_count,
        duration=result.duration,
    )


@router.get(
    "/search",
    response_model=YTDLPSearchResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        400: COMMON_ERROR_RESPONSES[400],
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Search YouTube for videos",
    description="""
Search YouTube for music videos by artist and track title.

Uses yt-dlp to query YouTube and returns metadata for matching videos.
Results are sorted by relevance. The search query combines artist and track
title for best results.

**Example query:** `artist=Nirvana&track_title=Smells Like Teen Spirit&max_results=5`
    """,
)
async def search_youtube(
    current_user: Annotated[UserInfo, Depends(require_auth)],
    artist: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Artist name to search for",
    ),
    track_title: str = Query(
        ...,
        min_length=1,
        max_length=200,
        description="Track/song title to search for",
    ),
    max_results: int = Query(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of results to return",
    ),
) -> YTDLPSearchResponse:
    """Search YouTube for music videos."""
    logger.info(
        "ytdlp_api_search",
        artist=artist,
        track_title=track_title,
        max_results=max_results,
        user=current_user.username if current_user else "anonymous",
    )

    ytdlp_config = _get_ytdlp_config()

    try:
        async with YTDLPClient.from_config(ytdlp_config) as client:
            results = await client.search(
                artist=artist,
                track_title=track_title,
                max_results=max_results,
            )

        video_infos = [_convert_to_video_info(r) for r in results]
        query = f"{artist} {track_title}"

        return YTDLPSearchResponse(
            results=video_infos,
            query=query,
            total=len(video_infos),
        )

    except YTDLPNotFoundError as e:
        logger.error("ytdlp_not_found", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="yt-dlp binary not found. Please ensure yt-dlp is installed.",
        )
    except YTDLPExecutionError as e:
        logger.error("ytdlp_execution_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"YouTube search failed: {e}",
        )
    except YTDLPError as e:
        logger.error("ytdlp_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"yt-dlp error: {e}",
        )


@router.get(
    "/info/{video_id}",
    response_model=YTDLPVideoInfoResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        404: COMMON_ERROR_RESPONSES[404],
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Get video metadata",
    description="""
Get detailed metadata for a single YouTube video.

Accepts either a YouTube video ID (e.g., `dQw4w9WgXcQ`) or a full URL.
Returns video title, channel, view count, duration, and other metadata.
    """,
)
async def get_video_info(
    video_id: str,
    current_user: Annotated[UserInfo, Depends(require_auth)],
) -> YTDLPVideoInfoResponse:
    """Get metadata for a single YouTube video."""
    logger.info(
        "ytdlp_api_get_info",
        video_id=video_id,
        user=current_user.username if current_user else "anonymous",
    )

    ytdlp_config = _get_ytdlp_config()

    try:
        async with YTDLPClient.from_config(ytdlp_config) as client:
            result = await client.get_video_info(video_id)

        video_info = _convert_to_video_info(result)
        return YTDLPVideoInfoResponse(video=video_info)

    except YTDLPNotFoundError as e:
        logger.error("ytdlp_not_found", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="yt-dlp binary not found. Please ensure yt-dlp is installed.",
        )
    except YTDLPExecutionError as e:
        logger.error("ytdlp_execution_error", video_id=video_id, error=str(e))
        # Check if video not found vs other error
        if "Video unavailable" in str(e) or "Private video" in str(e):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video not found or unavailable: {video_id}",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video info: {e}",
        )
    except YTDLPError as e:
        logger.error("ytdlp_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"yt-dlp error: {e}",
        )


@router.post(
    "/download",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **AUTH_ERROR_RESPONSES,
        400: COMMON_ERROR_RESPONSES[400],
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Download a YouTube video",
    description="""
Submit a YouTube video download job.

The download runs as a background job. Connect to `/ws/jobs/{job_id}` for
real-time progress updates via WebSocket.

**Path validation:** The `output_path` must be within the configured library
directory. Relative paths are resolved relative to the library directory.

**Progress tracking:** Progress updates include download percentage, speed,
and ETA. Subscribe to the WebSocket endpoint to receive real-time updates.

**Cancellation:** Use `DELETE /ytdlp/download/{job_id}` to cancel an
in-progress download.
    """,
)
async def download_video(
    request: YTDLPDownloadRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
) -> JobResponse:
    """Submit a YouTube video download job."""
    # Validate output path is within library directory
    validated_path = _validate_download_path(request.output_path)

    logger.info(
        "ytdlp_api_download_submit",
        url=request.url,
        output_path=str(validated_path),
        user=current_user.username if current_user else "anonymous",
    )

    queue = get_job_queue()

    # Create download job
    job = Job(
        type=JobType.DOWNLOAD_YOUTUBE,
        metadata={
            "url": request.url,
            "output_path": str(validated_path),
            "format_spec": request.format_spec,
        },
    )

    try:
        await queue.submit(job)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    logger.info(
        "ytdlp_download_job_submitted",
        job_id=job.id,
        url=request.url,
    )

    return JobResponse.model_validate(job)


@router.delete(
    "/download/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **AUTH_ERROR_RESPONSES,
        400: COMMON_ERROR_RESPONSES[400],
        404: COMMON_ERROR_RESPONSES[404],
    },
    summary="Cancel a download",
    description="""
Cancel an in-progress YouTube video download.

Cancellation is cooperative - the download will stop at the next progress
check. Already downloaded data may be partially saved or cleaned up.

Returns 204 No Content on successful cancellation.
Returns 400 if the job has already completed, failed, or been cancelled.
Returns 404 if the job does not exist.
    """,
)
async def cancel_download(
    job_id: str,
    current_user: Annotated[UserInfo, Depends(require_auth)],
) -> None:
    """Cancel an in-progress download job."""
    logger.info(
        "ytdlp_api_cancel_download",
        job_id=job_id,
        user=current_user.username if current_user else "anonymous",
    )

    queue = get_job_queue()

    # Check if job exists
    job = await queue.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    # Verify it's a YouTube download job
    if job.type != JobType.DOWNLOAD_YOUTUBE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job {job_id} is not a YouTube download job",
        )

    # Attempt cancellation
    cancelled = await queue.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not found or already completed/failed/cancelled",
        )

    logger.info("ytdlp_download_cancelled", job_id=job_id)
