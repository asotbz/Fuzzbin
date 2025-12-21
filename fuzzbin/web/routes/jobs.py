"""Job management endpoints."""

from typing import Annotated, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from fuzzbin.auth.schemas import UserInfo
from fuzzbin.tasks import Job, JobStatus, JobType, get_job_queue
from fuzzbin.web.dependencies import get_current_user
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
    job_type: Optional[JobType] = Query(
        None, alias="type", description="Filter by job type"
    ),
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

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
