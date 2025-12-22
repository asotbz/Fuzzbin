"""Job management request/response schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from fuzzbin.tasks.models import JobStatus, JobType


class JobSubmitRequest(BaseModel):
    """Request to submit a new background job.

    Attributes:
        type: Type of job to run
        metadata: Job-specific parameters (varies by job type)

    Example:
        >>> request = JobSubmitRequest(
        ...     type=JobType.IMPORT_NFO,
        ...     metadata={"directory": "/path/to/nfos", "recursive": True}
        ... )
    """

    type: JobType
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobResponse(BaseModel):
    """Job status response.

    Contains all job information including progress and results.
    """

    id: str
    type: JobType
    status: JobStatus
    progress: float
    current_step: str
    total_items: int
    processed_items: int
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    metadata: dict[str, Any]

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    """List of jobs response."""

    jobs: list[JobResponse]
    total: int


class JobProgressUpdate(BaseModel):
    """Real-time progress update (WebSocket message).

    Sent periodically via WebSocket to update clients on job progress.
    """

    job_id: str
    status: JobStatus
    progress: float
    current_step: str
    processed_items: int
    total_items: int
    error: str | None = None
    result: dict[str, Any] | None = None


class JobTypeMetricsResponse(BaseModel):
    """Metrics for a specific job type."""

    job_type: JobType
    total_jobs: int
    completed: int
    failed: int
    cancelled: int
    timeout: int
    success_rate: float
    avg_duration_seconds: float
    total_duration_seconds: float


class JobMetricsResponse(BaseModel):
    """Overall job queue metrics response.

    Provides monitoring data for the job queue including:
    - Job counts by status
    - Success rate and average duration
    - Queue depth
    - Per-type breakdowns
    """

    total_jobs: int = Field(description="Total number of jobs ever submitted")
    pending_jobs: int = Field(description="Jobs waiting in queue")
    waiting_jobs: int = Field(description="Jobs waiting for dependencies")
    running_jobs: int = Field(description="Currently executing jobs")
    completed_jobs: int = Field(description="Successfully completed jobs")
    failed_jobs: int = Field(description="Failed jobs")
    cancelled_jobs: int = Field(description="Cancelled jobs")
    timeout_jobs: int = Field(description="Timed out jobs")
    success_rate: float = Field(description="Ratio of completed to terminal jobs (0.0-1.0)")
    avg_duration_seconds: float = Field(description="Average duration of completed jobs in seconds")
    queue_depth: int = Field(description="Current queue depth (pending jobs)")
    by_type: dict[str, JobTypeMetricsResponse] = Field(
        description="Metrics broken down by job type"
    )
    oldest_pending_age_seconds: float | None = Field(
        description="Age of the oldest pending job in seconds"
    )
    last_failure_at: datetime | None = Field(description="When the last job failed")
    last_completion_at: datetime | None = Field(description="When the last job completed")
