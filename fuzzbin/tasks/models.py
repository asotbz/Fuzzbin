"""Background task models and enums."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class JobType(str, Enum):
    """Job type enumeration."""

    IMPORT_NFO = "import_nfo"
    IMPORT_SPOTIFY = "import_spotify"
    DOWNLOAD_YOUTUBE = "download_youtube"
    FILE_ORGANIZE = "file_organize"
    FILE_DUPLICATE_RESOLVE = "file_duplicate_resolve"
    METADATA_ENRICH = "metadata_enrich"


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(BaseModel):
    """Background job model.

    Represents a background task with progress tracking and lifecycle management.

    Attributes:
        id: Unique job identifier (UUID)
        type: Type of job (e.g., import_nfo, download_youtube)
        status: Current job status
        progress: Progress percentage (0.0 to 1.0)
        current_step: Human-readable description of current operation
        total_items: Total number of items to process
        processed_items: Number of items processed so far
        result: Job result data (on completion)
        error: Error message (on failure)
        created_at: When the job was created
        started_at: When the job started running
        completed_at: When the job finished (completed/failed/cancelled)
        metadata: Job-specific parameters
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: JobType
    status: JobStatus = JobStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    current_step: str = "Initializing..."
    total_items: int = 0
    processed_items: int = 0
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def update_progress(self, processed: int, total: int, step: str) -> None:
        """Update job progress.

        Args:
            processed: Number of items processed
            total: Total number of items
            step: Human-readable current step description
        """
        self.processed_items = processed
        self.total_items = total
        self.current_step = step
        self.progress = processed / total if total > 0 else 0.0

    def mark_running(self) -> None:
        """Mark job as running."""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self, result: dict[str, Any]) -> None:
        """Mark job as completed.

        Args:
            result: Job result data
        """
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.result = result
        self.progress = 1.0

    def mark_failed(self, error: str) -> None:
        """Mark job as failed.

        Args:
            error: Error message describing the failure
        """
        self.status = JobStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error = error

    def mark_cancelled(self) -> None:
        """Mark job as cancelled."""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)

    @property
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state.

        Returns:
            True if job is completed, failed, or cancelled
        """
        return self.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        )
