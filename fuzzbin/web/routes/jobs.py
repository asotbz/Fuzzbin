"""Job management endpoints.

Includes:
- Job submission, listing, status, cancellation
- Scheduled task management (create, update, list, delete)
"""

from datetime import datetime
from typing import Annotated, Any, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from fuzzbin.auth.schemas import UserInfo
from fuzzbin.core.db import VideoRepository
from fuzzbin.core.db.repository import QueryError
from fuzzbin.tasks import Job, JobStatus, JobType, get_job_queue
from fuzzbin.tasks.queue import parse_cron
from fuzzbin.web.dependencies import get_current_user, get_repository, require_auth
from fuzzbin.web.schemas.common import AUTH_ERROR_RESPONSES, COMMON_ERROR_RESPONSES
from fuzzbin.web.schemas.jobs import (
    JobListResponse,
    JobMetricsResponse,
    JobResponse,
    JobSubmitRequest,
    JobTypeMetricsResponse,
)

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Submit a background job",
    description="Submit a new background job for async processing. Returns 202 Accepted with job details.",
)
async def submit_job(
    request: JobSubmitRequest,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> JobResponse:
    """Submit a new background job.

    The job will be queued and processed by a background worker.
    Connect to `/ws/jobs/{job_id}` for real-time progress updates.
    """
    queue = get_job_queue()

    # Create job
    job = Job(
        type=request.type,
        metadata=request.metadata,
    )

    try:
        await queue.submit(job)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    logger.info(
        "job_submitted_via_api",
        job_id=job.id,
        job_type=job.type.value,
        user=current_user.username if current_user else "anonymous",
    )
    return JobResponse.model_validate(job)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List jobs",
    description="List all jobs with optional status filter.",
)
async def list_jobs(
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
    job_status: Optional[JobStatus] = Query(
        None, alias="status", description="Filter by job status"
    ),
    job_type: Optional[JobType] = Query(None, alias="type", description="Filter by job type"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum jobs to return"),
) -> JobListResponse:
    """List all jobs with optional filtering."""
    queue = get_job_queue()
    jobs = await queue.list_jobs(status=job_status, job_type=job_type, limit=limit)

    return JobListResponse(
        jobs=[JobResponse.model_validate(j) for j in jobs],
        total=len(jobs),
    )


@router.get(
    "/metrics",
    response_model=JobMetricsResponse,
    summary="Get job queue metrics",
    description="Get monitoring metrics for the job queue including success rate, "
    "average duration, queue depth, and per-type breakdowns.",
)
async def get_metrics(
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> JobMetricsResponse:
    """Get job queue metrics for monitoring.

    Returns metrics including:
    - Job counts by status (pending, running, completed, failed, etc.)
    - Success rate (completed / terminal jobs)
    - Average job duration
    - Queue depth
    - Per-job-type metrics
    - Age of oldest pending job
    - Last failure and completion times
    """
    queue = get_job_queue()
    metrics = queue.get_metrics()

    # Convert by_type to response format
    by_type_response = {
        jt.value: JobTypeMetricsResponse(
            job_type=jt,
            total_jobs=tm.total_jobs,
            completed=tm.completed,
            failed=tm.failed,
            cancelled=tm.cancelled,
            timeout=tm.timeout,
            success_rate=tm.success_rate,
            avg_duration_seconds=tm.avg_duration_seconds,
            total_duration_seconds=tm.total_duration_seconds,
        )
        for jt, tm in metrics.by_type.items()
    }

    return JobMetricsResponse(
        total_jobs=metrics.total_jobs,
        pending_jobs=metrics.pending_jobs,
        waiting_jobs=metrics.waiting_jobs,
        running_jobs=metrics.running_jobs,
        completed_jobs=metrics.completed_jobs,
        failed_jobs=metrics.failed_jobs,
        cancelled_jobs=metrics.cancelled_jobs,
        timeout_jobs=metrics.timeout_jobs,
        success_rate=metrics.success_rate,
        avg_duration_seconds=metrics.avg_duration_seconds,
        queue_depth=metrics.queue_depth,
        by_type=by_type_response,
        oldest_pending_age_seconds=metrics.oldest_pending_age_seconds,
        last_failure_at=metrics.last_failure_at,
        last_completion_at=metrics.last_completion_at,
    )


# ==================== Scheduled Task Schemas ====================


class ScheduledTaskCreate(BaseModel):
    """Request to create a scheduled task."""

    name: str = Field(..., min_length=1, max_length=200, description="Task name")
    job_type: JobType = Field(..., description="Type of job to run")
    cron_expression: str = Field(
        ...,
        description="Cron expression (5 fields: min hour day month weekday)",
        examples=["0 * * * *", "0 0 * * *", "*/15 * * * *"],
    )
    enabled: bool = Field(default=True, description="Whether task is enabled")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata for the job")


class ScheduledTaskUpdate(BaseModel):
    """Request to update a scheduled task."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    cron_expression: Optional[str] = Field(None)
    enabled: Optional[bool] = Field(None)
    metadata: Optional[dict] = Field(None)


class ScheduledTaskResponse(BaseModel):
    """Scheduled task response."""

    id: int
    name: str
    job_type: str
    cron_expression: str
    enabled: bool
    metadata: Optional[dict] = Field(default=None)
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_error: Optional[str] = None
    run_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("metadata", mode="before")
    @classmethod
    def parse_metadata_json(cls, v: Any) -> Optional[dict]:
        """Parse metadata_json string into dict."""
        if v is None:
            return None
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    @classmethod
    def from_db_row(cls, row: dict) -> "ScheduledTaskResponse":
        """Create from database row, mapping metadata_json to metadata."""
        data = dict(row)
        if "metadata_json" in data:
            data["metadata"] = data.pop("metadata_json")
        return cls(**data)


class ScheduledTaskListResponse(BaseModel):
    """List of scheduled tasks."""

    tasks: List[ScheduledTaskResponse]
    total: int


# ==================== Scheduled Task Endpoints ====================


@router.post(
    "/scheduled",
    response_model=ScheduledTaskResponse,
    status_code=status.HTTP_201_CREATED,
    responses={**AUTH_ERROR_RESPONSES, 400: COMMON_ERROR_RESPONSES[400]},
    summary="Create scheduled task",
    description="Create a new scheduled task with cron expression.",
)
async def create_scheduled_task(
    request: ScheduledTaskCreate,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> ScheduledTaskResponse:
    """Create a new scheduled task."""
    # Validate cron expression
    from datetime import timezone

    next_run = parse_cron(request.cron_expression, datetime.now(timezone.utc))
    if next_run is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cron expression: {request.cron_expression}",
        )

    import json

    metadata_json = json.dumps(request.metadata) if request.metadata else None
    task_id = await repo.create_scheduled_task(
        name=request.name,
        job_type=request.job_type.value,
        cron_expression=request.cron_expression,
        enabled=request.enabled,
        metadata_json=metadata_json,
    )

    # Fetch the created task
    task = await repo.get_scheduled_task_by_id(task_id)

    logger.info(
        "scheduled_task_created",
        task_id=task_id,
        name=request.name,
        job_type=request.job_type.value,
        cron=request.cron_expression,
        user=current_user.username if current_user else "anonymous",
    )

    return ScheduledTaskResponse.from_db_row(task)


@router.get(
    "/scheduled",
    response_model=ScheduledTaskListResponse,
    summary="List scheduled tasks",
    description="List all scheduled tasks with optional filtering.",
)
async def list_scheduled_tasks(
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
    repo: VideoRepository = Depends(get_repository),
    enabled_only: bool = Query(False, description="Only return enabled tasks"),
) -> ScheduledTaskListResponse:
    """List all scheduled tasks."""
    tasks = await repo.get_scheduled_tasks(enabled_only=enabled_only)

    return ScheduledTaskListResponse(
        tasks=[ScheduledTaskResponse.from_db_row(t) for t in tasks],
        total=len(tasks),
    )


@router.get(
    "/scheduled/{task_id}",
    response_model=ScheduledTaskResponse,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Get scheduled task",
    description="Get a scheduled task by ID.",
)
async def get_scheduled_task(
    task_id: int,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
    repo: VideoRepository = Depends(get_repository),
) -> ScheduledTaskResponse:
    """Get scheduled task by ID."""
    try:
        task = await repo.get_scheduled_task_by_id(task_id)
    except QueryError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled task {task_id} not found",
            )
        raise

    return ScheduledTaskResponse.from_db_row(task)


@router.patch(
    "/scheduled/{task_id}",
    response_model=ScheduledTaskResponse,
    responses={
        **AUTH_ERROR_RESPONSES,
        400: COMMON_ERROR_RESPONSES[400],
        404: COMMON_ERROR_RESPONSES[404],
    },
    summary="Update scheduled task",
    description="Update a scheduled task's settings.",
)
async def update_scheduled_task(
    task_id: int,
    request: ScheduledTaskUpdate,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> ScheduledTaskResponse:
    """Update a scheduled task."""
    # Check task exists
    try:
        existing = await repo.get_scheduled_task_by_id(task_id)
    except QueryError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled task {task_id} not found",
            )
        raise

    # Validate cron if provided
    if request.cron_expression:
        from datetime import timezone

        next_run = parse_cron(request.cron_expression, datetime.now(timezone.utc))
        if next_run is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cron expression: {request.cron_expression}",
            )

    updates = request.model_dump(exclude_unset=True)
    await repo.update_scheduled_task(task_id, **updates)

    # Fetch updated task
    task = await repo.get_scheduled_task_by_id(task_id)

    logger.info(
        "scheduled_task_updated",
        task_id=task_id,
        updates=list(updates.keys()),
        user=current_user.username if current_user else "anonymous",
    )

    return ScheduledTaskResponse.from_db_row(task)


@router.delete(
    "/scheduled/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Delete scheduled task",
    description="Delete a scheduled task.",
)
async def delete_scheduled_task(
    task_id: int,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Delete a scheduled task."""
    try:
        await repo.delete_scheduled_task(task_id)
    except QueryError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled task {task_id} not found",
            )
        raise

    logger.info(
        "scheduled_task_deleted",
        task_id=task_id,
        user=current_user.username if current_user else "anonymous",
    )


@router.post(
    "/scheduled/{task_id}/run",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Run scheduled task now",
    description="Manually trigger a scheduled task to run immediately.",
)
async def run_scheduled_task_now(
    task_id: int,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> JobResponse:
    """Manually run a scheduled task immediately."""
    try:
        task = await repo.get_scheduled_task_by_id(task_id)
    except QueryError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scheduled task {task_id} not found",
            )
        raise

    queue = get_job_queue()

    # Create job from scheduled task - parse metadata_json if it's a string
    task_metadata = task.get("metadata_json") or task.get("metadata") or {}
    if isinstance(task_metadata, str):
        import json

        try:
            task_metadata = json.loads(task_metadata)
        except json.JSONDecodeError:
            task_metadata = {}

    job = Job(
        type=JobType(task["job_type"]),
        metadata=task_metadata,
    )

    try:
        await queue.submit(job)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    logger.info(
        "scheduled_task_triggered_manually",
        task_id=task_id,
        job_id=job.id,
        user=current_user.username if current_user else "anonymous",
    )

    return JobResponse.model_validate(job)


# ==================== Single Job Routes ====================
# NOTE: /{job_id} routes MUST come LAST to avoid matching /scheduled, /metrics paths


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job status",
    description="Get the current status and progress of a job.",
)
async def get_job(
    job_id: str,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> JobResponse:
    """Get job status by ID."""
    queue = get_job_queue()
    job = await queue.get_job(job_id)

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return JobResponse.model_validate(job)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a job",
    description="Cancel a pending or running job. Has no effect on completed jobs.",
)
async def cancel_job(
    job_id: str,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> None:
    """Cancel a pending or running job."""
    queue = get_job_queue()

    cancelled = await queue.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not found or already completed/failed/cancelled",
        )

    logger.info(
        "job_cancelled_via_api",
        job_id=job_id,
        user=current_user.username if current_user else "anonymous",
    )
