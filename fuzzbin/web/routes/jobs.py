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
    JobGroupListResponse,
    JobGroupResponse,
    JobHistoryResponse,
    JobListResponse,
    JobMetricsResponse,
    JobResponse,
    JobRetryResponse,
    JobSubmitRequest,
    JobTypeMetricsResponse,
    MaintenanceJobsResponse,
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
    description="List jobs from database with optional status/type filtering and pagination.",
)
async def list_jobs(
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
    repository: Annotated[VideoRepository, Depends(get_repository)],
    status: Optional[str] = Query(
        None,
        description="Comma-separated status filter (e.g., 'pending,running' or 'completed,failed')",
    ),
    job_type: Optional[str] = Query(
        None,
        alias="type",
        description="Comma-separated job type filter",
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum jobs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> JobListResponse:
    """List jobs from database with filtering and pagination.

    This endpoint fetches jobs from the persistent database, not just in-memory.
    Use status filter to get specific job states:
    - Active jobs: status=pending,waiting,running
    - Completed: status=completed
    - Failed: status=failed,cancelled,timeout
    """
    # Parse comma-separated filters
    statuses = [s.strip() for s in status.split(",")] if status else None
    job_types = [t.strip() for t in job_type.split(",")] if job_type else None

    jobs, total = await repository.get_jobs(
        statuses=statuses,
        job_types=job_types,
        limit=limit,
        offset=offset,
    )

    # Convert DB rows to JobResponse
    job_responses = []
    for job_row in jobs:
        job_responses.append(
            JobResponse(
                id=job_row["id"],
                type=JobType(job_row["type"]),
                status=JobStatus(job_row["status"]),
                progress=job_row["progress"],
                current_step=job_row.get("current_step", ""),
                total_items=job_row.get("total_items", 0),
                processed_items=job_row.get("processed_items", 0),
                result=job_row.get("result"),
                error=job_row.get("error"),
                created_at=job_row["created_at"],
                started_at=job_row.get("started_at"),
                completed_at=job_row.get("completed_at"),
                metadata=job_row.get("metadata", {}),
                video_id=job_row.get("video_id"),
                video_title=job_row.get("video_title"),
                video_artist=job_row.get("video_artist"),
            )
        )

    return JobListResponse(
        jobs=job_responses,
        total=total,
        limit=limit,
        offset=offset,
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
        await repo.get_scheduled_task_by_id(task_id)
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


# ==================== Job Groups Endpoints ====================


@router.get(
    "/groups",
    response_model=JobGroupListResponse,
    summary="List job groups by video",
    description="Get active jobs grouped by video_id. Each group shows all jobs "
    "related to a single video (download, process, organize, etc.).",
)
async def list_job_groups(
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
    repo: VideoRepository = Depends(get_repository),
    include_jobs: bool = Query(True, description="Include individual jobs in each group"),
) -> JobGroupListResponse:
    """List active job groups aggregated by video_id."""
    # Get active groups from database
    groups_data = await repo.get_active_job_groups()

    groups = []
    for group in groups_data:
        # Parse job_types from comma-separated string
        job_types = group.get("job_types", "").split(",") if group.get("job_types") else []

        # Get individual jobs if requested
        jobs = []
        if include_jobs and group.get("video_id"):
            job_rows = await repo.get_jobs_by_video_id(group["video_id"])
            # Only include non-terminal jobs for active groups
            for job_row in job_rows:
                if job_row.get("status") in ("pending", "waiting", "running"):
                    jobs.append(
                        JobResponse(
                            id=job_row["id"],
                            type=JobType(job_row["type"]),
                            status=JobStatus(job_row["status"]),
                            progress=job_row.get("progress", 0.0),
                            current_step=job_row.get("current_step", ""),
                            total_items=job_row.get("total_items", 0),
                            processed_items=job_row.get("processed_items", 0),
                            result=job_row.get("result"),
                            error=job_row.get("error"),
                            created_at=datetime.fromisoformat(job_row["created_at"]),
                            started_at=datetime.fromisoformat(job_row["started_at"])
                            if job_row.get("started_at")
                            else None,
                            completed_at=datetime.fromisoformat(job_row["completed_at"])
                            if job_row.get("completed_at")
                            else None,
                            metadata=job_row.get("metadata", {}),
                            video_id=job_row.get("video_id"),
                        )
                    )

        groups.append(
            JobGroupResponse(
                video_id=group["video_id"],
                video_title=group.get("video_title"),
                video_artist=group.get("video_artist"),
                job_count=group.get("job_count", 0),
                completed_count=group.get("completed_count", 0),
                running_count=group.get("running_count", 0),
                pending_count=group.get("pending_count", 0),
                failed_count=group.get("failed_count", 0),
                overall_progress=group.get("overall_progress", 0.0),
                group_status=group.get("group_status", "pending"),
                job_types=job_types,
                first_created_at=datetime.fromisoformat(group["first_created_at"])
                if group.get("first_created_at")
                else datetime.now(),
                current_started_at=datetime.fromisoformat(group["current_started_at"])
                if group.get("current_started_at")
                else None,
                jobs=jobs,
            )
        )

    return JobGroupListResponse(groups=groups, total=len(groups))


@router.delete(
    "/groups/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel all jobs for a video",
    description="Cancel all pending/waiting jobs associated with a video.",
)
async def cancel_video_jobs(
    video_id: int,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Cancel all pending/waiting jobs for a video."""
    cancelled_count = await repo.cancel_jobs_by_video_id(video_id)

    logger.info(
        "video_jobs_cancelled_via_api",
        video_id=video_id,
        cancelled_count=cancelled_count,
        user=current_user.username if current_user else "anonymous",
    )


# ==================== Job History Endpoints ====================


@router.get(
    "/history",
    response_model=JobHistoryResponse,
    summary="Get job history",
    description="Get paginated history of completed, failed, cancelled, and timed out jobs.",
)
async def get_job_history(
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
    repo: VideoRepository = Depends(get_repository),
    status_filter: Optional[List[str]] = Query(
        None,
        alias="status",
        description="Filter by status (completed, failed, cancelled, timeout)",
    ),
    type_filter: Optional[List[str]] = Query(
        None,
        alias="type",
        description="Filter by job type",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
) -> JobHistoryResponse:
    """Get paginated job history."""
    offset = (page - 1) * page_size

    job_rows, total = await repo.get_job_history(
        status_filter=status_filter,
        job_type_filter=type_filter,
        limit=page_size,
        offset=offset,
    )

    jobs = []
    for job_row in job_rows:
        jobs.append(
            JobResponse(
                id=job_row["id"],
                type=JobType(job_row["type"]),
                status=JobStatus(job_row["status"]),
                progress=job_row.get("progress", 0.0),
                current_step=job_row.get("current_step", ""),
                total_items=job_row.get("total_items", 0),
                processed_items=job_row.get("processed_items", 0),
                result=job_row.get("result"),
                error=job_row.get("error"),
                created_at=datetime.fromisoformat(job_row["created_at"]),
                started_at=datetime.fromisoformat(job_row["started_at"])
                if job_row.get("started_at")
                else None,
                completed_at=datetime.fromisoformat(job_row["completed_at"])
                if job_row.get("completed_at")
                else None,
                metadata=job_row.get("metadata", {}),
                video_id=job_row.get("video_id"),
                video_title=job_row.get("video_title"),
                video_artist=job_row.get("video_artist"),
            )
        )

    total_pages = (total + page_size - 1) // page_size

    return JobHistoryResponse(
        jobs=jobs,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "/{job_id}/retry",
    response_model=JobRetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry a failed job",
    description="Create a new job with the same parameters as a failed job.",
)
async def retry_job(
    job_id: str,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
) -> JobRetryResponse:
    """Retry a failed job by creating a new job with the same parameters."""
    queue = get_job_queue()

    new_job_id = await queue.retry_job(job_id)

    if not new_job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job not found or not in a retriable state (must be failed, timeout, or cancelled)",
        )

    # Get the original job to return job type
    original_job = await queue.get_job(job_id)
    job_type = original_job.type if original_job else JobType.IMPORT_NFO

    logger.info(
        "job_retried_via_api",
        original_job_id=job_id,
        new_job_id=new_job_id,
        user=current_user.username if current_user else "anonymous",
    )

    return JobRetryResponse(
        original_job_id=job_id,
        new_job_id=new_job_id,
        job_type=job_type,
    )


# ==================== Maintenance Jobs Endpoint ====================


@router.get(
    "/maintenance",
    response_model=MaintenanceJobsResponse,
    summary="Get maintenance jobs",
    description="Get active maintenance jobs (backup, trash cleanup, job history cleanup, etc.) "
    "and scheduled task information.",
)
async def get_maintenance_jobs(
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
    repo: VideoRepository = Depends(get_repository),
) -> MaintenanceJobsResponse:
    """Get maintenance jobs and scheduled tasks."""
    # Get active maintenance jobs from database
    job_rows = await repo.get_maintenance_jobs(include_completed=False)

    active_jobs = []
    for job_row in job_rows:
        active_jobs.append(
            JobResponse(
                id=job_row["id"],
                type=JobType(job_row["type"]),
                status=JobStatus(job_row["status"]),
                progress=job_row.get("progress", 0.0),
                current_step=job_row.get("current_step", ""),
                total_items=job_row.get("total_items", 0),
                processed_items=job_row.get("processed_items", 0),
                result=job_row.get("result"),
                error=job_row.get("error"),
                created_at=datetime.fromisoformat(job_row["created_at"]),
                started_at=datetime.fromisoformat(job_row["started_at"])
                if job_row.get("started_at")
                else None,
                completed_at=datetime.fromisoformat(job_row["completed_at"])
                if job_row.get("completed_at")
                else None,
                metadata=job_row.get("metadata", {}),
            )
        )

    # Get scheduled tasks
    scheduled_tasks = await repo.get_scheduled_tasks(enabled_only=True)

    return MaintenanceJobsResponse(
        active_jobs=active_jobs,
        scheduled_jobs=scheduled_tasks,
    )
