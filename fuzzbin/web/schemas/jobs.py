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
