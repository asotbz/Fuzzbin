"""Backup management endpoints.

Provides API endpoints for:
- Triggering on-demand backups
- Listing available backups
- Downloading backup archives
- Verifying backup integrity
"""

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

import fuzzbin
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.services.backup_service import BackupService
from fuzzbin.tasks import Job, JobType, get_job_queue
from fuzzbin.web.dependencies import require_auth
from fuzzbin.web.schemas.backup import (
    BackupCreateRequest,
    BackupCreateResponse,
    BackupInfo,
    BackupListResponse,
    BackupVerifyResponse,
)
from fuzzbin.web.schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/backup", tags=["Backup"])


@router.post(
    "",
    response_model=BackupCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        **AUTH_ERROR_RESPONSES,
        500: COMMON_ERROR_RESPONSES[500],
    },
    summary="Create backup",
    description="""Trigger an on-demand system backup.

Creates a background job that generates a .zip archive containing:
- **config.yaml**: User configuration file
- **fuzzbin.db**: Library database (using SQLite backup API)
- **.thumbnails/**: Cached thumbnail images

The backup job runs asynchronously. Use the returned `job_id` to track
progress via `GET /jobs/{job_id}` or WebSocket `/ws/jobs/{job_id}`.

Old backups exceeding the retention count are automatically deleted.""",
)
async def create_backup(
    request: BackupCreateRequest,
    current_user: Annotated[UserInfo, Depends(require_auth)],
) -> BackupCreateResponse:
    """Submit a backup job.

    Creates a background job to generate a complete system backup.
    """
    queue = get_job_queue()
    config = fuzzbin.get_config()

    # Create backup job with optional description
    job = Job(
        type=JobType.BACKUP,
        metadata={
            "description": request.description,
            "retention_count": config.backup.retention_count,
        },
    )

    await queue.submit(job)

    logger.info(
        "backup_job_submitted",
        job_id=job.id,
        user=current_user.username if current_user else "anonymous",
        description=request.description,
    )

    return BackupCreateResponse(
        job_id=job.id,
        message="Backup job submitted successfully",
    )


@router.get(
    "",
    response_model=BackupListResponse,
    responses={**AUTH_ERROR_RESPONSES},
    summary="List backups",
    description="""List all available backup archives.

Returns backup metadata including filename, size, creation timestamp,
and contents. Results are sorted by creation time (newest first).""",
)
async def list_backups(
    current_user: Annotated[UserInfo, Depends(require_auth)],
) -> BackupListResponse:
    """List all available backups."""
    config = fuzzbin.get_config()
    backup_service = BackupService(config)

    backups = backup_service.list_backups()

    return BackupListResponse(
        backups=[
            BackupInfo(
                filename=b["filename"],
                size_bytes=b["size_bytes"],
                created_at=b["created_at"],
                contains=b["contains"],
            )
            for b in backups
        ],
        total=len(backups),
    )


@router.get(
    "/{filename}",
    response_class=FileResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        404: COMMON_ERROR_RESPONSES[404],
    },
    summary="Download backup",
    description="""Download a backup archive by filename.

Returns the .zip file as a binary download. The archive can be
extracted and restored manually without the program running.""",
)
async def download_backup(
    filename: str,
    current_user: Annotated[UserInfo, Depends(require_auth)],
) -> FileResponse:
    """Download a backup archive.

    Returns the .zip file for the specified backup.
    """
    config = fuzzbin.get_config()
    backup_service = BackupService(config)

    backup_path = backup_service.get_backup_path(filename)

    if backup_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup not found: {filename}",
        )

    logger.info(
        "backup_downloaded",
        filename=filename,
        user=current_user.username if current_user else "anonymous",
    )

    return FileResponse(
        path=backup_path,
        filename=filename,
        media_type="application/zip",
    )


@router.get(
    "/{filename}/verify",
    response_model=BackupVerifyResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        404: COMMON_ERROR_RESPONSES[404],
    },
    summary="Verify backup integrity",
    description="""Verify a backup archive's integrity.

Checks:
- ZIP file structure and CRC checksums
- Database SQLite integrity (if database is included)
- Presence of expected files

Returns verification results including any errors found.""",
)
async def verify_backup(
    filename: str,
    current_user: Annotated[UserInfo, Depends(require_auth)],
) -> BackupVerifyResponse:
    """Verify backup integrity.

    Checks the archive structure and database integrity.
    """
    config = fuzzbin.get_config()
    backup_service = BackupService(config)

    try:
        result = await backup_service.verify_backup(filename)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backup not found: {filename}",
        )

    return BackupVerifyResponse(
        valid=result["valid"],
        filename=result["filename"],
        contains=result["contains"],
        database_valid=result["database_valid"],
        errors=result["errors"],
    )
