"""Backup API request/response schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BackupInfo(BaseModel):
    """Information about a backup archive.

    Returned when listing or creating backups.
    """

    filename: str = Field(
        description="Name of the backup file (e.g., 'fuzzbin_backup_20251222_140530.zip')",
        examples=["fuzzbin_backup_20251222_140530.zip"],
    )
    size_bytes: int = Field(
        description="Size of the backup archive in bytes",
        examples=[15728640],
    )
    created_at: str = Field(
        description="ISO 8601 timestamp when the backup was created",
        examples=["2025-12-22T14:05:30+00:00"],
    )
    contains: List[str] = Field(
        description="List of items included in backup: 'config', 'database', 'thumbnails'",
        examples=[["config", "database", "thumbnails"]],
    )


class BackupListResponse(BaseModel):
    """Response containing list of available backups."""

    backups: List[BackupInfo] = Field(
        description="List of available backup archives, sorted by creation time (newest first)"
    )
    total: int = Field(
        description="Total number of backups available",
        examples=[7],
    )


class BackupCreateRequest(BaseModel):
    """Request to create a new backup."""

    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional description for the backup",
        examples=["Pre-upgrade backup"],
    )


class BackupCreateResponse(BaseModel):
    """Response when a backup job is submitted.

    The backup runs as a background job. Poll the job status endpoint
    for progress and completion.
    """

    job_id: str = Field(
        description="ID of the background backup job",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    message: str = Field(
        description="Human-readable status message",
        examples=["Backup job submitted successfully"],
    )


class BackupVerifyResponse(BaseModel):
    """Response from backup verification."""

    valid: bool = Field(
        description="True if backup passed all integrity checks"
    )
    filename: str = Field(
        description="Name of the verified backup file"
    )
    contains: List[str] = Field(
        description="List of items found in backup: 'config', 'database', 'thumbnails'"
    )
    database_valid: Optional[bool] = Field(
        default=None,
        description="True if database passed SQLite integrity check (null if no database in backup)"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of error messages if verification failed"
    )
