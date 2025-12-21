"""File management endpoints for organizing, deleting, and verifying media files."""

from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from fuzzbin.auth import UserInfo
from fuzzbin.services import VideoService
from fuzzbin.services.base import (
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)

from ..dependencies import get_video_service, require_auth

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/files", tags=["Files"])


# ==================== Schemas ====================


class OrganizeRequest(BaseModel):
    """Request body for organizing a video."""

    dry_run: bool = Field(
        default=False,
        description="If true, only return target paths without moving files",
    )


class OrganizeResponse(BaseModel):
    """Response for organize operation."""

    video_id: int
    source_video_path: Optional[str] = None
    target_video_path: str
    target_nfo_path: str
    dry_run: bool
    status: str = Field(description="'moved', 'already_organized', or 'dry_run'")


class DeleteRequest(BaseModel):
    """Request body for deleting a video's files."""

    hard_delete: bool = Field(
        default=False,
        description="If true, permanently delete files. If false, move to trash.",
    )


class DeleteResponse(BaseModel):
    """Response for delete operation."""

    video_id: int
    deleted: bool
    hard_delete: bool
    trash_path: Optional[str] = None


class RestoreRequest(BaseModel):
    """Request body for restoring a video from trash."""

    restore_path: Optional[str] = Field(
        default=None,
        description="Custom restore path. If not provided, restores to original location.",
    )


class RestoreResponse(BaseModel):
    """Response for restore operation."""

    video_id: int
    restored: bool
    restored_path: str


class DuplicateResponse(BaseModel):
    """Response for a single duplicate candidate."""

    video_id: int
    match_type: str = Field(description="'hash', 'metadata', or 'both'")
    confidence: float = Field(ge=0.0, le=1.0)
    title: Optional[str] = None
    artist: Optional[str] = None
    file_path: Optional[str] = None
    file_hash: Optional[str] = None


class DuplicatesResponse(BaseModel):
    """Response for duplicates endpoint."""

    video_id: int
    duplicates: List[DuplicateResponse]
    total: int


class ResolveRequest(BaseModel):
    """Request to resolve duplicates."""

    keep_video_id: int = Field(description="ID of the video to keep")
    remove_video_ids: List[int] = Field(description="IDs of duplicate videos to remove")
    hard_delete: bool = Field(
        default=False,
        description="If true, permanently delete. If false, soft delete.",
    )


class ResolveResponse(BaseModel):
    """Response for resolve operation."""

    kept_video_id: int
    removed_count: int
    removed_video_ids: List[int]


class LibraryIssueResponse(BaseModel):
    """Response for a single library issue."""

    issue_type: str
    video_id: Optional[int] = None
    path: Optional[str] = None
    message: str
    repair_action: Optional[str] = None


class VerifyResponse(BaseModel):
    """Response for library verification."""

    videos_checked: int
    files_scanned: int
    missing_files: int
    orphaned_files: int
    broken_nfos: int
    path_mismatches: int
    total_issues: int
    issues: List[LibraryIssueResponse]


class RepairRequest(BaseModel):
    """Request to repair library issues."""

    repair_missing_files: bool = Field(
        default=True,
        description="Update status to 'missing' for videos with missing files",
    )
    repair_broken_nfos: bool = Field(
        default=True,
        description="Clear NFO path for videos with missing NFO files",
    )


class RepairResponse(BaseModel):
    """Response for repair operation."""

    repaired_missing_files: int
    repaired_broken_nfos: int
    total_repaired: int


# ==================== Routes ====================


@router.post(
    "/videos/{video_id}/organize",
    response_model=OrganizeResponse,
    summary="Organize video files",
    description="Move video (and NFO) files to organized location based on path pattern.",
    responses={
        200: {"description": "Files organized successfully"},
        404: {"description": "Video not found"},
        409: {"description": "Target path already exists"},
        500: {"description": "File operation failed"},
    },
)
async def organize_video(
    video_id: int,
    request: OrganizeRequest = None,
    user: Optional[UserInfo] = Depends(require_auth),
    video_service: VideoService = Depends(get_video_service),
) -> OrganizeResponse:
    """
    Organize a video's files using the configured path pattern.

    Moves the video file (and associated NFO) to a structured location
    based on metadata fields like artist and title.

    Use dry_run=true to preview the target paths without actually moving files.
    """
    if request is None:
        request = OrganizeRequest()

    try:
        result = await video_service.organize(
            video_id=video_id,
            dry_run=request.dry_run,
        )

        return OrganizeResponse(
            video_id=result.video_id,
            source_video_path=result.source_video_path,
            target_video_path=result.target_video_path,
            target_nfo_path=result.target_nfo_path,
            dry_run=result.dry_run,
            status=result.status,
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e.message),
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e.message),
        )
    except ServiceError as e:
        logger.error("organize_failed", video_id=video_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e.message),
        )


@router.delete(
    "/videos/{video_id}",
    response_model=DeleteResponse,
    summary="Delete video files",
    description="Delete video files (soft delete to trash or hard delete permanently).",
    responses={
        200: {"description": "Files deleted successfully"},
        404: {"description": "Video not found"},
        500: {"description": "Delete operation failed"},
    },
)
async def delete_video_files(
    video_id: int,
    hard_delete: bool = Query(
        default=False,
        description="If true, permanently delete files",
    ),
    user: Optional[UserInfo] = Depends(require_auth),
    video_service: VideoService = Depends(get_video_service),
) -> DeleteResponse:
    """
    Delete a video's files.

    By default, performs a soft delete by moving files to the trash directory.
    Use hard_delete=true to permanently remove files.
    """
    try:
        result = await video_service.delete_files(
            video_id=video_id,
            hard_delete=hard_delete,
        )

        return DeleteResponse(
            video_id=result.video_id,
            deleted=result.deleted,
            hard_delete=result.hard_delete,
            trash_path=result.trash_path,
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
        logger.error("delete_failed", video_id=video_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e.message),
        )


@router.post(
    "/videos/{video_id}/restore",
    response_model=RestoreResponse,
    summary="Restore video from trash",
    description="Restore a soft-deleted video from the trash directory.",
    responses={
        200: {"description": "Video restored successfully"},
        404: {"description": "Video not found or not in trash"},
        409: {"description": "Restore target already exists"},
        500: {"description": "Restore operation failed"},
    },
)
async def restore_video(
    video_id: int,
    request: RestoreRequest = None,
    user: Optional[UserInfo] = Depends(require_auth),
    video_service: VideoService = Depends(get_video_service),
) -> RestoreResponse:
    """
    Restore a video that was soft-deleted to the trash.

    By default, restores to the original location. Provide restore_path
    to specify a different location.
    """
    if request is None:
        request = RestoreRequest()

    try:
        result = await video_service.restore_files(
            video_id=video_id,
            restore_path=request.restore_path,
        )

        return RestoreResponse(
            video_id=result.video_id,
            restored=result.restored,
            restored_path=result.restored_path,
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
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e.message),
        )
    except ServiceError as e:
        logger.error("restore_failed", video_id=video_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e.message),
        )


@router.get(
    "/videos/{video_id}/duplicates",
    response_model=DuplicatesResponse,
    summary="Find duplicate videos",
    description="Find potential duplicate videos by hash and/or metadata.",
    responses={
        200: {"description": "Duplicates found (may be empty list)"},
        404: {"description": "Video not found"},
    },
)
async def find_duplicates(
    video_id: int,
    method: str = Query(
        default="all",
        description="Detection method: 'hash', 'metadata', or 'all'",
    ),
    user: Optional[UserInfo] = Depends(require_auth),
    video_service: VideoService = Depends(get_video_service),
) -> DuplicatesResponse:
    """
    Find potential duplicates of a video.

    Methods:
    - 'hash': Find videos with matching file hash (exact duplicates)
    - 'metadata': Find videos with matching title/artist (potential duplicates)
    - 'all': Use both methods, merge results
    """
    try:
        result = await video_service.find_duplicates(
            video_id=video_id,
            method=method,
        )

        duplicates = [
            DuplicateResponse(
                video_id=d.video_id,
                match_type=d.match_type,
                confidence=d.confidence,
                title=d.video_data.get("title"),
                artist=d.video_data.get("artist"),
                file_path=d.video_data.get("video_file_path"),
                file_hash=d.video_data.get("file_hash"),
            )
            for d in result.duplicates
        ]

        return DuplicatesResponse(
            video_id=result.video_id,
            duplicates=duplicates,
            total=result.total,
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e.message),
        )
    except ServiceError as e:
        logger.error("find_duplicates_failed", video_id=video_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e.message),
        )


@router.post(
    "/duplicates/resolve",
    response_model=ResolveResponse,
    summary="Resolve duplicate videos",
    description="Keep one video and remove the duplicates.",
    responses={
        200: {"description": "Duplicates resolved"},
        404: {"description": "Video not found"},
        500: {"description": "Resolution failed"},
    },
)
async def resolve_duplicates(
    request: ResolveRequest,
    user: Optional[UserInfo] = Depends(require_auth),
    video_service: VideoService = Depends(get_video_service),
) -> ResolveResponse:
    """
    Resolve duplicates by keeping one video and removing others.

    The kept video is unchanged. Duplicate videos are either soft deleted
    (moved to trash) or hard deleted (permanently removed).
    """
    try:
        result = await video_service.resolve_duplicates(
            keep_video_id=request.keep_video_id,
            remove_video_ids=request.remove_video_ids,
            hard_delete=request.hard_delete,
        )

        return ResolveResponse(
            kept_video_id=result.kept_video_id,
            removed_count=result.removed_count,
            removed_video_ids=result.removed_video_ids,
        )

    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e.message),
        )
    except ServiceError as e:
        logger.error("resolve_duplicates_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e.message),
        )


@router.get(
    "/library/verify",
    response_model=VerifyResponse,
    summary="Verify library integrity",
    description="Scan database and filesystem to find missing files, orphans, and broken links.",
    responses={
        200: {"description": "Verification complete"},
        500: {"description": "Verification failed"},
    },
)
async def verify_library(
    scan_orphans: bool = Query(
        default=True,
        description="Also scan for files not in database",
    ),
    user: Optional[UserInfo] = Depends(require_auth),
    video_service: VideoService = Depends(get_video_service),
) -> VerifyResponse:
    """
    Verify library integrity by checking database paths against filesystem.

    Checks:
    - Videos in DB have existing files on disk
    - NFO paths in DB point to existing files
    - (Optional) Files in workspace that aren't tracked in DB
    """
    try:
        report = await video_service.verify_library()

        return VerifyResponse(
            videos_checked=report.videos_checked,
            files_scanned=report.files_scanned,
            missing_files=report.missing_files,
            orphaned_files=report.orphaned_files,
            broken_nfos=report.broken_nfos,
            path_mismatches=report.path_mismatches,
            total_issues=len(report.issues),
            issues=[
                LibraryIssueResponse(
                    issue_type=issue.issue_type,
                    video_id=issue.video_id,
                    path=issue.path,
                    message=issue.message,
                    repair_action=issue.repair_action,
                )
                for issue in report.issues
            ],
        )

    except ServiceError as e:
        logger.error("library_verification_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e.message),
        )


@router.post(
    "/library/repair",
    response_model=RepairResponse,
    summary="Repair library issues",
    description="Automatically repair issues found during verification.",
    responses={
        200: {"description": "Repairs completed"},
        500: {"description": "Repair failed"},
    },
)
async def repair_library(
    request: RepairRequest = None,
    user: Optional[UserInfo] = Depends(require_auth),
    video_service: VideoService = Depends(get_video_service),
) -> RepairResponse:
    """
    Repair library issues found during verification.

    Repairs:
    - Missing files: Update video status to 'missing'
    - Broken NFOs: Clear NFO path in database
    """
    if request is None:
        request = RepairRequest()

    try:
        result = await video_service.repair_library(
            repair_missing=request.repair_missing_files,
            repair_broken_nfos=request.repair_broken_nfos,
        )

        return RepairResponse(
            repaired_missing_files=result.get("repaired_missing_files", 0),
            repaired_broken_nfos=result.get("repaired_broken_nfos", 0),
            total_repaired=result.get("total_repaired", 0),
        )

    except ServiceError as e:
        logger.error("library_repair_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e.message),
        )
