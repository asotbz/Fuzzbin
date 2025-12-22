"""Bulk operation endpoints for videos (Phase 7)."""

from typing import Annotated, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

import fuzzbin
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.core.db import VideoRepository

from ..dependencies import get_repository, require_auth
from ..schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/videos/bulk", tags=["Bulk Operations"])


# ==================== Request/Response Schemas ====================


class BulkOperationResult(BaseModel):
    """Response for bulk operations showing success/failure per ID."""

    success_ids: List[int] = Field(default_factory=list, description="IDs that succeeded")
    failed_ids: List[int] = Field(default_factory=list, description="IDs that failed")
    errors: dict = Field(default_factory=dict, description="Error messages keyed by ID")
    total: int = Field(description="Total items processed")
    success_count: int = Field(description="Number of successful operations")
    failed_count: int = Field(description="Number of failed operations")

    @classmethod
    def from_repo_result(cls, result: dict) -> "BulkOperationResult":
        """Create from repository result dict."""
        return cls(
            success_ids=result.get("success_ids", []),
            failed_ids=result.get("failed_ids", []),
            errors=result.get("errors", {}),
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
    hard_delete: bool = Field(
        default=False, description="Permanently delete (True) or soft delete (False)"
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


async def _get_max_bulk_items() -> int:
    """Get configured max bulk items limit."""
    config = fuzzbin.get_config()
    return config.advanced.max_bulk_items


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
    description="Delete multiple videos (soft delete by default, hard delete optional).",
)
async def bulk_delete_videos(
    request: BulkDeleteRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> BulkOperationResult:
    """Bulk delete videos."""
    max_items = await _get_max_bulk_items()
    _validate_bulk_limit(len(request.video_ids), max_items)

    result = await repo.bulk_delete_videos(
        video_ids=request.video_ids,
        hard_delete=request.hard_delete,
    )

    logger.info(
        "bulk_delete_completed",
        user=current_user.username if current_user else "anonymous",
        total=len(request.video_ids),
        success=len(result["success_ids"]),
        failed=len(result["failed_ids"]),
        hard_delete=request.hard_delete,
    )

    return BulkOperationResult.from_repo_result(result)


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
