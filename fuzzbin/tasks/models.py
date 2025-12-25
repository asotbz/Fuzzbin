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
    IMPORT_ADD_SINGLE = "import_add_single"
    IMPORT_DOWNLOAD = "import_download"  # Download video from YouTube
    IMPORT_ORGANIZE = "import_organize"  # Organize video file to library structure
    IMPORT_NFO_GENERATE = "import_nfo_generate"  # Generate NFO file for imported video
    DOWNLOAD_YOUTUBE = "download_youtube"
    FILE_ORGANIZE = "file_organize"
    FILE_DUPLICATE_RESOLVE = "file_duplicate_resolve"
    METADATA_ENRICH = "metadata_enrich"
    METADATA_REFRESH = "metadata_refresh"  # Phase 7: Scheduled metadata refresh
    LIBRARY_SCAN = "library_scan"  # Phase 7: Scheduled library scan
    IMPORT = "import"  # Phase 7: Generic import job (YouTube/IMVDb)
    BACKUP = "backup"  # System backup job


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    WAITING = "waiting"  # Waiting for dependencies
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class JobPriority(int, Enum):
    """Job priority levels.

    Higher values = higher priority (processed first).
    """

    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class Job(BaseModel):
    """Background job model.

    Represents a background task with progress tracking and lifecycle management.

    Attributes:
        id: Unique job identifier (UUID)
        type: Type of job (e.g., import_nfo, download_youtube)
        status: Current job status
        priority: Job priority (higher = processed first)
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
        timeout_seconds: Maximum execution time (None = no timeout)
        depends_on: List of job IDs that must complete before this job runs
        schedule: Cron expression for scheduled jobs (None = run immediately)
        next_run_at: Next scheduled run time (for scheduled jobs)
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: JobType
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
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

    # Advanced features
    timeout_seconds: int | None = Field(
        default=None, description="Maximum execution time in seconds"
    )
    depends_on: list[str] = Field(
        default_factory=list, description="Job IDs that must complete first"
    )
    parent_job_id: str | None = Field(
        default=None, description="ID of parent job if this is a child job in a workflow"
    )
    schedule: str | None = Field(
        default=None, description="Cron expression for scheduled execution"
    )
    next_run_at: datetime | None = Field(default=None, description="Next scheduled run time")

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

    def mark_waiting(self) -> None:
        """Mark job as waiting for dependencies."""
        self.status = JobStatus.WAITING

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

    def mark_timeout(self) -> None:
        """Mark job as timed out."""
        self.status = JobStatus.TIMEOUT
        self.completed_at = datetime.now(timezone.utc)
        self.error = f"Job exceeded timeout of {self.timeout_seconds} seconds"

    @property
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state.

        Returns:
            True if job is completed, failed, cancelled, or timed out
        """
        return self.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.TIMEOUT,
        )

    def __lt__(self, other: "Job") -> bool:
        """Compare jobs for priority queue ordering.

        Higher priority jobs come first. For equal priorities,
        older jobs (earlier created_at) come first.
        """
        if self.priority != other.priority:
            # Higher priority value = higher priority
            return self.priority.value > other.priority.value
        # Equal priority: older jobs first (FIFO within same priority)
        return self.created_at < other.created_at
