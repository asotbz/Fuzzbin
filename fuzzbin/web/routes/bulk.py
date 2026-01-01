"""Bulk operation endpoints for videos (Phase 7)."""

from typing import Annotated, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

import fuzzbin
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.core.db import VideoRepository
from fuzzbin.services import VideoService

from ..dependencies import get_repository, get_video_service, require_auth
from ..schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES, BulkOperationResponse

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/videos/bulk", tags=["Bulk Operations"])


# ==================== Request/Response Schemas ====================


class BulkOperationResult(BaseModel):
    """Response for bulk operations showing success/failure per ID."""

    success_ids: List[int] = Field(default_factory=list, description="IDs that succeeded")
    failed_ids: List[int] = Field(default_factory=list, description="IDs that failed")
    errors: dict = Field(default_factory=dict, description="Error messages keyed by ID")
    file_errors: List[str] = Field(
        default_factory=list, description="File deletion errors (non-fatal)"
    )
    total: int = Field(description="Total items processed")
    success_count: int = Field(description="Number of successful operations")
    failed_count: int = Field(description="Number of failed operations")

    @classmethod
    def from_repo_result(cls, result: dict, file_errors: List[str] = None) -> "BulkOperationResult":
        """Create from repository result dict."""
        return cls(
            success_ids=result.get("success_ids", []),
            failed_ids=result.get("failed_ids", []),
            errors=result.get("errors", {}),
            file_errors=file_errors or [],
            total=len(result.get("success_ids", [])) + len(result.get("failed_ids", [])),
            success_count=len(result.get("success_ids", [])),
            failed_count=len(result.get("failed_ids", [])),
        )


class BulkUpdateRequest(BaseModel):
    """Request for bulk updating videos."""

    video_ids: List[int] = Field(..., min_length=1, description="Video IDs to update")
    updates: dict = Field(
        ...,
        description="Fields to update (same as VideoUpdate schema)",
        examples=[{"genre": "Rock", "studio": "Universal"}],
    )


class BulkDeleteRequest(BaseModel):
    """Request for bulk deleting videos."""

    video_ids: List[int] = Field(..., min_length=1, description="Video IDs to delete")
    permanent: bool = Field(
        default=False, description="Permanently delete DB records (True) or soft delete (False)"
    )
    delete_files: bool = Field(
        default=False, description="Also delete video/NFO files from disk (moved to trash)"
    )


class BulkStatusRequest(BaseModel):
    """Request for bulk status update."""

    video_ids: List[int] = Field(..., min_length=1, description="Video IDs to update")
    status: str = Field(
        ...,
        description="New status value",
        examples=["organized", "archived", "failed"],
    )
    reason: Optional[str] = Field(default=None, description="Reason for status change")


class BulkTagsRequest(BaseModel):
    """Request for bulk tag application."""

    video_ids: List[int] = Field(..., min_length=1, description="Video IDs to tag")
    tag_names: List[str] = Field(
        ..., min_length=1, description="Tag names to apply", examples=[["rock", "90s", "mtv"]]
    )
    replace: bool = Field(
        default=False, description="Replace existing tags (True) or add to them (False)"
    )


class BulkCollectionRequest(BaseModel):
    """Request for bulk collection assignment."""

    video_ids: List[int] = Field(..., min_length=1, description="Video IDs to add")
    collection_id: int = Field(..., description="Collection ID to add videos to")


class BulkOrganizeItem(BaseModel):
    """Single item for bulk organize request."""

    video_id: int = Field(..., description="Video ID")
    video_file_path: str = Field(..., description="New video file path")
    nfo_file_path: Optional[str] = Field(default=None, description="New NFO file path")


class BulkOrganizeRequest(BaseModel):
    """Request for bulk file path updates after organization."""

    items: List[BulkOrganizeItem] = Field(
        ..., min_length=1, description="Videos with new file paths"
    )


# ==================== Helper Functions ====================

# Default max bulk items limit
DEFAULT_MAX_BULK_ITEMS = 500


async def _get_max_bulk_items() -> int:
    """Get configured max bulk items limit."""
    return DEFAULT_MAX_BULK_ITEMS


def _validate_bulk_limit(count: int, max_items: int) -> None:
    """Validate bulk operation doesn't exceed limit."""
    if count > max_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bulk operation exceeds limit: {count} > {max_items} max items",
        )


# ==================== Endpoints ====================


@router.post(
    "/update",
    response_model=BulkOperationResult,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Bulk update videos",
    description="Update multiple videos with the same field values in a single transaction.",
)
async def bulk_update_videos(
    request: BulkUpdateRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> BulkOperationResult:
    """Bulk update videos with same field values."""
    max_items = await _get_max_bulk_items()
    _validate_bulk_limit(len(request.video_ids), max_items)

    result = await repo.bulk_update_videos(
        video_ids=request.video_ids,
        updates=request.updates,
    )

    logger.info(
        "bulk_update_completed",
        user=current_user.username if current_user else "anonymous",
        total=len(request.video_ids),
        success=len(result["success_ids"]),
        failed=len(result["failed_ids"]),
    )

    return BulkOperationResult.from_repo_result(result)


@router.post(
    "/delete",
    response_model=BulkOperationResult,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Bulk delete videos",
    description="Delete multiple videos. Optionally also delete files from disk (moved to trash).",
)
async def bulk_delete_videos(
    request: BulkDeleteRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
    video_service: VideoService = Depends(get_video_service),
) -> BulkOperationResult:
    """Bulk delete videos.

    - permanent=False (default): Soft delete DB records (can be restored)
    - permanent=True: Permanently delete DB records
    - delete_files=True: Also delete video/NFO files from disk (moved to trash)
    """
    max_items = await _get_max_bulk_items()
    _validate_bulk_limit(len(request.video_ids), max_items)

    file_errors: List[str] = []

    # Delete files first if requested (before DB deletion)
    if request.delete_files:
        for video_id in request.video_ids:
            try:
                await video_service.delete_files(video_id=video_id, hard_delete=False)
            except Exception as e:
                # Log error but continue with remaining videos
                error_msg = f"Video {video_id}: {str(e)}"
                file_errors.append(error_msg)
                logger.warning(
                    "bulk_delete_file_error",
                    video_id=video_id,
                    error=str(e),
                )

    # Delete DB records
    result = await repo.bulk_delete_videos(
        video_ids=request.video_ids,
        hard_delete=request.permanent,
    )

    logger.info(
        "bulk_delete_completed",
        user=current_user.username if current_user else "anonymous",
        total=len(request.video_ids),
        success=len(result["success_ids"]),
        failed=len(result["failed_ids"]),
        permanent=request.permanent,
        delete_files=request.delete_files,
        file_errors_count=len(file_errors),
    )

    return BulkOperationResult.from_repo_result(result, file_errors=file_errors)


@router.post(
    "/status",
    response_model=BulkOperationResult,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Bulk update status",
    description="Update status for multiple videos in a single transaction.",
)
async def bulk_update_status(
    request: BulkStatusRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> BulkOperationResult:
    """Bulk update video status."""
    max_items = await _get_max_bulk_items()
    _validate_bulk_limit(len(request.video_ids), max_items)

    result = await repo.bulk_update_status(
        video_ids=request.video_ids,
        new_status=request.status,
        reason=request.reason,
        changed_by=f"bulk_api:{current_user.username if current_user else 'anonymous'}",
    )

    logger.info(
        "bulk_status_update_completed",
        user=current_user.username if current_user else "anonymous",
        total=len(request.video_ids),
        success=len(result["success_ids"]),
        failed=len(result["failed_ids"]),
        new_status=request.status,
    )

    return BulkOperationResult.from_repo_result(result)


@router.post(
    "/tags",
    response_model=BulkOperationResult,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Bulk apply tags",
    description="Apply tags to multiple videos. Can add to existing tags or replace them.",
)
async def bulk_apply_tags(
    request: BulkTagsRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> BulkOperationResult:
    """Bulk apply tags to videos."""
    max_items = await _get_max_bulk_items()
    _validate_bulk_limit(len(request.video_ids), max_items)

    result = await repo.bulk_apply_tags(
        video_ids=request.video_ids,
        tag_names=request.tag_names,
        replace=request.replace,
    )

    logger.info(
        "bulk_tags_applied",
        user=current_user.username if current_user else None,
        total=len(request.video_ids),
        success=len(result["success_ids"]),
        failed=len(result["failed_ids"]),
        tags=request.tag_names,
        replace=request.replace,
    )

    return BulkOperationResult.from_repo_result(result)


@router.post(
    "/collections",
    response_model=BulkOperationResult,
    responses={
        **AUTH_ERROR_RESPONSES,
        400: COMMON_ERROR_RESPONSES[400],
        404: COMMON_ERROR_RESPONSES[404],
    },
    summary="Bulk add to collection",
    description="Add multiple videos to a collection in a single transaction.",
)
async def bulk_add_to_collection(
    request: BulkCollectionRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> BulkOperationResult:
    """Bulk add videos to a collection."""
    max_items = await _get_max_bulk_items()
    _validate_bulk_limit(len(request.video_ids), max_items)

    result = await repo.bulk_add_to_collection(
        video_ids=request.video_ids,
        collection_id=request.collection_id,
    )

    logger.info(
        "bulk_collection_add_completed",
        user=current_user.username if current_user else "anonymous",
        total=len(request.video_ids),
        success=len(result["success_ids"]),
        failed=len(result["failed_ids"]),
        collection_id=request.collection_id,
    )

    return BulkOperationResult.from_repo_result(result)


@router.post(
    "/organize",
    response_model=BulkOperationResult,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Bulk update file paths",
    description="Update file paths for multiple videos after file organization.",
)
async def bulk_organize_videos(
    request: BulkOrganizeRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> BulkOperationResult:
    """Bulk update video file paths after organization."""
    max_items = await _get_max_bulk_items()
    _validate_bulk_limit(len(request.items), max_items)

    # Convert to repository format
    video_updates = [item.model_dump() for item in request.items]

    result = await repo.bulk_organize_videos(video_updates=video_updates)

    logger.info(
        "bulk_organize_completed",
        user=current_user.username if current_user else "anonymous",
        total=len(request.items),
        success=len(result["success_ids"]),
        failed=len(result["failed_ids"]),
    )

    return BulkOperationResult.from_repo_result(result)


@router.post(
    "/download",
    response_model=BulkOperationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**COMMON_ERROR_RESPONSES, **AUTH_ERROR_RESPONSES},
    summary="Bulk download videos",
    description="Queue download jobs for multiple videos with YouTube IDs. Skips videos without YouTube IDs.",
)
async def bulk_download_videos(
    video_ids: List[int],
    repository: VideoRepository = Depends(get_repository),
) -> BulkOperationResponse:
    """Queue download jobs for multiple videos with YouTube IDs.

    Skips videos without YouTube IDs. Each video downloads to temp,
    organizes to configured path pattern, and generates NFO.
    """
    from fuzzbin.tasks.models import Job, JobType, JobPriority
    from fuzzbin.tasks.queue import get_job_queue

    queue = get_job_queue()
    submitted = []
    skipped = []

    for video_id in video_ids:
        video = await repository.get_video_by_id(video_id)
        if not video:
            skipped.append({"video_id": video_id, "reason": "Not found"})
            continue

        youtube_id = getattr(video, "youtube_id", None)
        if not youtube_id:
            skipped.append({"video_id": video_id, "reason": "No YouTube ID"})
            continue

        # Queue IMPORT_DOWNLOAD job
        job = Job(
            type=JobType.IMPORT_DOWNLOAD,
            metadata={
                "video_id": video_id,
                "youtube_id": youtube_id,
            },
            priority=JobPriority.NORMAL,
        )
        await queue.submit(job)
        submitted.append(job.id)

    logger.info(
        "bulk_download_queued",
        total=len(video_ids),
        submitted=len(submitted),
        skipped=len(skipped),
    )

    return BulkOperationResponse(
        submitted=len(submitted),
        skipped=len(skipped),
        job_ids=submitted,
        details={"skipped_videos": skipped} if skipped else None,
    )
