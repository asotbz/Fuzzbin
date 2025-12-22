"""Import workflow endpoints (Phase 7).

Provides endpoints for:
- YouTube direct import (search + download)
- IMVDb bulk metadata import
"""

from dataclasses import dataclass, field
from typing import Annotated, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

import fuzzbin
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.core.db import VideoRepository
from fuzzbin.tasks import JobType, get_job_queue

from ..dependencies import get_repository, require_auth
from ..schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/imports", tags=["Imports"])


# ==================== Request/Response Schemas ====================


class YouTubeImportRequest(BaseModel):
    """Request for YouTube import."""

    urls: List[str] = Field(
        ...,
        min_length=1,
        description="YouTube video URLs to import",
        examples=[["https://youtube.com/watch?v=abc123", "https://youtu.be/def456"]],
    )
    download_video: bool = Field(
        default=True, description="Download video files (False = metadata only)"
    )
    output_directory: Optional[str] = Field(
        default=None, description="Output directory for downloads (uses default if not specified)"
    )


class IMVDbImportRequest(BaseModel):
    """Request for IMVDb bulk import."""

    video_ids: Optional[List[int]] = Field(
        default=None,
        description="Specific IMVDb video IDs to import",
        examples=[[121779770452, 138862728833]],
    )
    search_queries: Optional[List[dict]] = Field(
        default=None,
        description="Search queries to find videos (artist + title pairs)",
        examples=[[{"artist": "Robin Thicke", "title": "Blurred Lines"}]],
    )


class ImportItemResult(BaseModel):
    """Result for a single import item."""

    identifier: str = Field(description="URL, ID, or search query identifier")
    success: bool = Field(description="Whether import succeeded")
    video_id: Optional[int] = Field(default=None, description="Created/updated video ID")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class ImportResult(BaseModel):
    """Result of an import operation."""

    total: int = Field(description="Total items processed")
    success_count: int = Field(description="Successful imports")
    failed_count: int = Field(description="Failed imports")
    items: List[ImportItemResult] = Field(description="Per-item results")
    job_id: Optional[str] = Field(
        default=None, description="Background job ID (if async processing)"
    )


# ==================== Helper Functions ====================


async def _get_max_sync_items() -> int:
    """Get configured max synchronous import items."""
    config = fuzzbin.get_config()
    return config.advanced.max_sync_import_items


def _is_background_available() -> bool:
    """Check if background task queue is available."""
    try:
        queue = get_job_queue()
        return queue is not None and queue.is_running
    except Exception:
        return False


# ==================== YouTube Import ====================


@router.post(
    "/youtube",
    response_model=ImportResult,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Import from YouTube",
    description="Import videos from YouTube URLs. Small batches run synchronously, "
    "larger batches require background task queue.",
)
async def import_from_youtube(
    request: YouTubeImportRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> ImportResult:
    """
    Import videos from YouTube.

    For small batches (under max_sync_import_items), runs synchronously.
    For larger batches, queues a background job if available.
    """
    max_sync = await _get_max_sync_items()

    if len(request.urls) > max_sync:
        # Check if background queue is available
        if _is_background_available():
            # Queue background job
            queue = get_job_queue()
            from fuzzbin.tasks import Job

            job = Job(
                type=JobType.IMPORT,
                metadata={
                    "import_type": "youtube",
                    "urls": request.urls,
                    "download_video": request.download_video,
                    "output_directory": request.output_directory,
                    "user": current_user.username if current_user else "anonymous",
                },
            )
            await queue.submit(job)

            logger.info(
                "youtube_import_queued",
                job_id=job.id,
                url_count=len(request.urls),
                user=current_user.username if current_user else "anonymous",
            )

            return ImportResult(
                total=len(request.urls),
                success_count=0,
                failed_count=0,
                items=[],
                job_id=job.id,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Import exceeds synchronous limit ({len(request.urls)} > {max_sync}). "
                "Background task queue not available.",
            )

    # Synchronous import for small batches
    items = []
    success_count = 0
    failed_count = 0

    for url in request.urls:
        try:
            # Extract video ID from URL
            video_id = _extract_youtube_id(url)
            if not video_id:
                items.append(
                    ImportItemResult(
                        identifier=url,
                        success=False,
                        error="Invalid YouTube URL",
                    )
                )
                failed_count += 1
                continue

            # Check if video already exists
            try:
                existing = await repo.get_video_by_youtube_id(video_id)
                items.append(
                    ImportItemResult(
                        identifier=url,
                        success=True,
                        video_id=existing["id"],
                        error="Already exists (skipped)",
                    )
                )
                success_count += 1
                continue
            except Exception:
                pass  # Video doesn't exist, continue with import

            # Create video record with YouTube ID
            # Note: Full metadata enrichment would require yt-dlp client integration
            db_video_id = await repo.create_video(
                title=f"YouTube Video {video_id}",  # Placeholder title
                youtube_id=video_id,
                status="discovered",
            )

            items.append(
                ImportItemResult(
                    identifier=url,
                    success=True,
                    video_id=db_video_id,
                )
            )
            success_count += 1

            logger.info(
                "youtube_video_imported",
                url=url,
                youtube_id=video_id,
                video_id=db_video_id,
            )

        except Exception as e:
            items.append(
                ImportItemResult(
                    identifier=url,
                    success=False,
                    error=str(e),
                )
            )
            failed_count += 1
            logger.error("youtube_import_failed", url=url, error=str(e))

    logger.info(
        "youtube_import_completed",
        total=len(request.urls),
        success=success_count,
        failed=failed_count,
        user=current_user.username if current_user else "anonymous",
    )

    return ImportResult(
        total=len(request.urls),
        success_count=success_count,
        failed_count=failed_count,
        items=items,
    )


def _extract_youtube_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from various URL formats."""
    import re

    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",  # Just the ID
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return None


# ==================== IMVDb Import ====================


@router.post(
    "/imvdb",
    response_model=ImportResult,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Import from IMVDb",
    description="Import video metadata from IMVDb by ID or search query.",
)
async def import_from_imvdb(
    request: IMVDbImportRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> ImportResult:
    """
    Import video metadata from IMVDb.

    Accepts either:
    - video_ids: List of specific IMVDb video IDs
    - search_queries: List of {artist, title} pairs to search

    For small batches, runs synchronously. Larger batches queue a background job.
    """
    # Calculate total items
    total_items = 0
    if request.video_ids:
        total_items += len(request.video_ids)
    if request.search_queries:
        total_items += len(request.search_queries)

    if total_items == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide video_ids or search_queries",
        )

    max_sync = await _get_max_sync_items()

    if total_items > max_sync:
        if _is_background_available():
            queue = get_job_queue()
            from fuzzbin.tasks import Job

            job = Job(
                type=JobType.IMPORT,
                metadata={
                    "import_type": "imvdb",
                    "video_ids": request.video_ids,
                    "search_queries": request.search_queries,
                    "user": current_user.username if current_user else "anonymous",
                },
            )
            await queue.submit(job)

            logger.info(
                "imvdb_import_queued",
                job_id=job.id,
                total_items=total_items,
                user=current_user.username if current_user else "anonymous",
            )

            return ImportResult(
                total=total_items,
                success_count=0,
                failed_count=0,
                items=[],
                job_id=job.id,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Import exceeds synchronous limit ({total_items} > {max_sync}). "
                "Background task queue not available.",
            )

    # Synchronous import
    items = []
    success_count = 0
    failed_count = 0

    # Import by video IDs
    if request.video_ids:
        for imvdb_id in request.video_ids:
            try:
                # Check if already exists
                try:
                    existing = await repo.get_video_by_imvdb_id(str(imvdb_id))
                    items.append(
                        ImportItemResult(
                            identifier=f"imvdb:{imvdb_id}",
                            success=True,
                            video_id=existing["id"],
                            error="Already exists (skipped)",
                        )
                    )
                    success_count += 1
                    continue
                except Exception:
                    pass

                # Create placeholder record
                # Note: Full metadata would require IMVDb client integration
                db_video_id = await repo.create_video(
                    title=f"IMVDb Video {imvdb_id}",
                    imvdb_video_id=str(imvdb_id),
                    status="discovered",
                )

                items.append(
                    ImportItemResult(
                        identifier=f"imvdb:{imvdb_id}",
                        success=True,
                        video_id=db_video_id,
                    )
                )
                success_count += 1

            except Exception as e:
                items.append(
                    ImportItemResult(
                        identifier=f"imvdb:{imvdb_id}",
                        success=False,
                        error=str(e),
                    )
                )
                failed_count += 1

    # Import by search queries
    if request.search_queries:
        for query in request.search_queries:
            artist = query.get("artist", "")
            title = query.get("title", "")
            identifier = f"{artist} - {title}"

            try:
                # Create placeholder record
                db_video_id = await repo.create_video(
                    title=title or "Unknown",
                    artist=artist or None,
                    status="discovered",
                )

                items.append(
                    ImportItemResult(
                        identifier=identifier,
                        success=True,
                        video_id=db_video_id,
                    )
                )
                success_count += 1

            except Exception as e:
                items.append(
                    ImportItemResult(
                        identifier=identifier,
                        success=False,
                        error=str(e),
                    )
                )
                failed_count += 1

    logger.info(
        "imvdb_import_completed",
        total=total_items,
        success=success_count,
        failed=failed_count,
        user=current_user.username if current_user else "anonymous",
    )

    return ImportResult(
        total=total_items,
        success_count=success_count,
        failed_count=failed_count,
        items=items,
    )
