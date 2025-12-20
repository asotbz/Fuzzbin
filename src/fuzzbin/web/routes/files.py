"""File management endpoints for organizing, deleting, and verifying media files."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

import fuzzbin
from fuzzbin.auth import UserInfo
from fuzzbin.core.db import VideoRepository
from fuzzbin.core.file_manager import (
    FileManager,
    FileManagerError,
    FileNotFoundError as FMFileNotFoundError,
    FileExistsError as FMFileExistsError,
    HashMismatchError,
    RollbackError,
    DuplicateCandidate,
    LibraryReport,
)
from fuzzbin.parsers.models import MusicVideoNFO

from ..dependencies import get_repository, require_auth

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


# ==================== Helper Functions ====================


async def get_file_manager() -> FileManager:
    """Get configured FileManager instance."""
    config = fuzzbin.get_config()
    
    workspace_root = Path(config.database.workspace_root or ".")
    
    return FileManager(
        config=config.file_manager,
        workspace_root=workspace_root,
        organizer_config=config.organizer,
    )


def nfo_from_video(video: Dict[str, Any]) -> MusicVideoNFO:
    """Create MusicVideoNFO from video database record."""
    return MusicVideoNFO(
        title=video.get("title", ""),
        artist=video.get("artist"),
        album=video.get("album"),
        year=video.get("year"),
        director=video.get("director"),
        genre=video.get("genre"),
        studio=video.get("studio"),
    )


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
    repo: VideoRepository = Depends(get_repository),
) -> OrganizeResponse:
    """
    Organize a video's files using the configured path pattern.
    
    Moves the video file (and associated NFO) to a structured location
    based on metadata fields like artist and title.
    
    Use dry_run=true to preview the target paths without actually moving files.
    """
    if request is None:
        request = OrganizeRequest()
    
    # Get video from database
    try:
        video = await repo.get_video_by_id(video_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {video_id}",
        )
    
    # Get file manager
    file_manager = await get_file_manager()
    
    # Create NFO data from video
    nfo_data = nfo_from_video(video)
    
    try:
        target_paths = await file_manager.organize_video(
            video_id=video_id,
            repository=repo,
            nfo_data=nfo_data,
            dry_run=request.dry_run,
        )
        
        # Determine status
        current_path = video.get("video_file_path")
        if str(target_paths.video_path) == current_path:
            op_status = "already_organized"
        elif request.dry_run:
            op_status = "dry_run"
        else:
            op_status = "moved"
        
        return OrganizeResponse(
            video_id=video_id,
            source_video_path=current_path,
            target_video_path=str(target_paths.video_path),
            target_nfo_path=str(target_paths.nfo_path),
            dry_run=request.dry_run,
            status=op_status,
        )
        
    except FMFileExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Target file already exists: {e.path}",
        )
    except FMFileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source file not found: {e.path}",
        )
    except HashMismatchError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File integrity check failed: {e}",
        )
    except RollbackError as e:
        logger.error(
            "organize_rollback_failed",
            video_id=video_id,
            error=str(e),
            original_error=str(e.original_error),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File operation failed and rollback failed: {e}",
        )
    except FileManagerError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File operation failed: {e}",
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
    repo: VideoRepository = Depends(get_repository),
) -> DeleteResponse:
    """
    Delete a video's files.
    
    By default, performs a soft delete by moving files to the trash directory.
    Use hard_delete=true to permanently remove files.
    """
    # Get video from database
    try:
        video = await repo.get_video_by_id(video_id, include_deleted=True)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {video_id}",
        )
    
    video_path = video.get("video_file_path")
    nfo_path = video.get("nfo_file_path")
    
    if not video_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video has no file path",
        )
    
    file_manager = await get_file_manager()
    
    try:
        if hard_delete:
            await file_manager.hard_delete(
                video_id=video_id,
                video_path=Path(video_path),
                repository=repo,
                nfo_path=Path(nfo_path) if nfo_path else None,
            )
            return DeleteResponse(
                video_id=video_id,
                deleted=True,
                hard_delete=True,
                trash_path=None,
            )
        else:
            trash_path = await file_manager.soft_delete(
                video_id=video_id,
                video_path=Path(video_path),
                repository=repo,
                nfo_path=Path(nfo_path) if nfo_path else None,
            )
            return DeleteResponse(
                video_id=video_id,
                deleted=True,
                hard_delete=False,
                trash_path=str(trash_path),
            )
            
    except FMFileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {e.path}",
        )
    except FileManagerError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Delete operation failed: {e}",
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
    repo: VideoRepository = Depends(get_repository),
) -> RestoreResponse:
    """
    Restore a video that was soft-deleted to the trash.
    
    By default, restores to the original location. Provide restore_path
    to specify a different location.
    """
    if request is None:
        request = RestoreRequest()
    
    # Get video including deleted
    try:
        video = await repo.get_video_by_id(video_id, include_deleted=True)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {video_id}",
        )
    
    if not video.get("is_deleted"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video is not deleted",
        )
    
    current_path = video.get("video_file_path")
    current_nfo_path = video.get("nfo_file_path")
    
    if not current_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video has no file path",
        )
    
    file_manager = await get_file_manager()
    config = fuzzbin.get_config()
    workspace_root = Path(config.database.workspace_root or ".")
    
    # Determine restore path
    if request.restore_path:
        restore_path = Path(request.restore_path)
        restore_nfo_path = restore_path.with_suffix(".nfo")
    else:
        # Try to restore to original location (before trash)
        # The path in DB is the trash path, so we need to calculate original
        trash_dir = workspace_root / config.file_manager.trash_dir
        try:
            relative = Path(current_path).relative_to(trash_dir)
            restore_path = workspace_root / relative
            restore_nfo_path = restore_path.with_suffix(".nfo")
        except ValueError:
            # Path isn't in trash - use as-is
            restore_path = Path(current_path)
            restore_nfo_path = Path(current_nfo_path) if current_nfo_path else None
    
    try:
        restored_path = await file_manager.restore(
            video_id=video_id,
            trash_video_path=Path(current_path),
            restore_path=restore_path,
            repository=repo,
            trash_nfo_path=Path(current_nfo_path) if current_nfo_path else None,
            restore_nfo_path=restore_nfo_path,
        )
        
        return RestoreResponse(
            video_id=video_id,
            restored=True,
            restored_path=str(restored_path),
        )
        
    except FMFileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trash file not found: {e.path}",
        )
    except FMFileExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Restore target already exists: {e.path}",
        )
    except FileManagerError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore operation failed: {e}",
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
    repo: VideoRepository = Depends(get_repository),
) -> DuplicatesResponse:
    """
    Find potential duplicates of a video.
    
    Methods:
    - 'hash': Find videos with matching file hash (exact duplicates)
    - 'metadata': Find videos with matching title/artist (potential duplicates)
    - 'all': Use both methods, merge results
    """
    # Verify video exists
    try:
        await repo.get_video_by_id(video_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video not found: {video_id}",
        )
    
    file_manager = await get_file_manager()
    
    try:
        if method == "hash":
            candidates = await file_manager.find_duplicates_by_hash(video_id, repo)
        elif method == "metadata":
            candidates = await file_manager.find_duplicates_by_metadata(video_id, repo)
        else:
            candidates = await file_manager.find_all_duplicates(video_id, repo)
        
        duplicates = [
            DuplicateResponse(
                video_id=c.video_id,
                match_type=c.match_type,
                confidence=c.confidence,
                title=c.video_data.get("title"),
                artist=c.video_data.get("artist"),
                file_path=c.video_data.get("video_file_path"),
                file_hash=c.video_data.get("file_hash"),
            )
            for c in candidates
        ]
        
        return DuplicatesResponse(
            video_id=video_id,
            duplicates=duplicates,
            total=len(duplicates),
        )
        
    except FileManagerError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Duplicate detection failed: {e}",
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
    repo: VideoRepository = Depends(get_repository),
) -> ResolveResponse:
    """
    Resolve duplicates by keeping one video and removing others.
    
    The kept video is unchanged. Duplicate videos are either soft deleted
    (moved to trash) or hard deleted (permanently removed).
    """
    # Verify keep video exists
    try:
        await repo.get_video_by_id(request.keep_video_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video to keep not found: {request.keep_video_id}",
        )
    
    file_manager = await get_file_manager()
    removed_ids = []
    
    for remove_id in request.remove_video_ids:
        try:
            video = await repo.get_video_by_id(remove_id)
            video_path = video.get("video_file_path")
            nfo_path = video.get("nfo_file_path")
            
            if video_path:
                if request.hard_delete:
                    await file_manager.hard_delete(
                        video_id=remove_id,
                        video_path=Path(video_path),
                        repository=repo,
                        nfo_path=Path(nfo_path) if nfo_path else None,
                    )
                else:
                    await file_manager.soft_delete(
                        video_id=remove_id,
                        video_path=Path(video_path),
                        repository=repo,
                        nfo_path=Path(nfo_path) if nfo_path else None,
                    )
            else:
                # No file path - just delete DB record
                if request.hard_delete:
                    await repo.hard_delete_video(remove_id)
                else:
                    await repo.delete_video(remove_id)
            
            removed_ids.append(remove_id)
            
        except Exception as e:
            logger.warning(
                "duplicate_removal_failed",
                video_id=remove_id,
                error=str(e),
            )
            # Continue with other removals
    
    return ResolveResponse(
        kept_video_id=request.keep_video_id,
        removed_count=len(removed_ids),
        removed_video_ids=removed_ids,
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
    repo: VideoRepository = Depends(get_repository),
) -> VerifyResponse:
    """
    Verify library integrity by checking database paths against filesystem.
    
    Checks:
    - Videos in DB have existing files on disk
    - NFO paths in DB point to existing files
    - (Optional) Files in workspace that aren't tracked in DB
    """
    file_manager = await get_file_manager()
    
    try:
        report = await file_manager.verify_library(
            repository=repo,
            scan_orphans=scan_orphans,
        )
        
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
        
    except Exception as e:
        logger.error("library_verification_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Library verification failed: {e}",
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
    repo: VideoRepository = Depends(get_repository),
) -> RepairResponse:
    """
    Repair library issues found during verification.
    
    Repairs:
    - Missing files: Update video status to 'missing'
    - Broken NFOs: Clear NFO path in database
    """
    if request is None:
        request = RepairRequest()
    
    file_manager = await get_file_manager()
    
    # First verify to find issues
    report = await file_manager.verify_library(
        repository=repo,
        scan_orphans=False,  # Don't need orphans for repair
    )
    
    repaired_missing = 0
    repaired_nfos = 0
    
    for issue in report.issues:
        try:
            if issue.issue_type == "missing_file" and request.repair_missing_files:
                if issue.video_id:
                    await file_manager.repair_missing_file(issue.video_id, repo)
                    repaired_missing += 1
                    
            elif issue.issue_type == "broken_nfo" and request.repair_broken_nfos:
                if issue.video_id:
                    await file_manager.repair_broken_nfo(issue.video_id, repo)
                    repaired_nfos += 1
                    
        except Exception as e:
            logger.warning(
                "repair_failed",
                issue_type=issue.issue_type,
                video_id=issue.video_id,
                error=str(e),
            )
    
    return RepairResponse(
        repaired_missing_files=repaired_missing,
        repaired_broken_nfos=repaired_nfos,
        total_repaired=repaired_missing + repaired_nfos,
    )
