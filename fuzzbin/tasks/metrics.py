"""Job queue monitoring and metrics.

This module provides monitoring capabilities for the background job queue:
- Job metrics (success rate, average duration, counts by status/type)
- Failed job alerts (callback/webhook system)
- Queue depth monitoring
- Historical statistics

Example:
    >>> from fuzzbin.tasks.metrics import JobMetrics, FailedJobAlert
    >>>
    >>> # Get metrics
    >>> metrics = job_queue.get_metrics()
    >>> print(f"Success rate: {metrics.success_rate * 100:.1f}%")
    >>> print(f"Average duration: {metrics.avg_duration_seconds:.1f}s")
    >>>
    >>> # Register alert callback
    >>> async def on_failure(alert: FailedJobAlert):
    ...     print(f"Job {alert.job_id} failed: {alert.error}")
    ...
    >>> job_queue.on_job_failed(on_failure)
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

from fuzzbin.tasks.models import Job, JobStatus, JobType

logger = structlog.get_logger(__name__)


@dataclass
class FailedJobAlert:
    """Alert data for a failed job.

    Attributes:
        job_id: ID of the failed job
        job_type: Type of the failed job
        error: Error message
        failed_at: When the job failed
        duration_seconds: How long the job ran before failing
        metadata: Original job metadata
    """

    job_id: str
    job_type: JobType
    error: str
    failed_at: datetime
    duration_seconds: float | None
    metadata: dict[str, Any]


@dataclass
class JobTypeMetrics:
    """Metrics for a specific job type.

    Attributes:
        job_type: The job type
        total_jobs: Total number of jobs of this type
        completed: Number of completed jobs
        failed: Number of failed jobs
        cancelled: Number of cancelled jobs
        timeout: Number of timed out jobs
        avg_duration_seconds: Average duration of completed jobs
        total_duration_seconds: Sum of all job durations
    """

    job_type: JobType
    total_jobs: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    timeout: int = 0
    avg_duration_seconds: float = 0.0
    total_duration_seconds: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate for this job type."""
        terminal = self.completed + self.failed + self.timeout
        if terminal == 0:
            return 0.0
        return self.completed / terminal


@dataclass
class JobMetrics:
    """Overall job queue metrics.

    Attributes:
        total_jobs: Total number of jobs ever submitted
        pending_jobs: Currently pending jobs
        waiting_jobs: Jobs waiting for dependencies
        running_jobs: Currently running jobs
        completed_jobs: Successfully completed jobs
        failed_jobs: Failed jobs
        cancelled_jobs: Cancelled jobs
        timeout_jobs: Timed out jobs
        success_rate: Ratio of completed to terminal jobs
        avg_duration_seconds: Average duration of completed jobs
        queue_depth: Current queue depth (pending + waiting)
        by_type: Per-job-type metrics
        oldest_pending_age_seconds: Age of oldest pending job
        last_failure_at: When the last job failed
        last_completion_at: When the last job completed
    """

    total_jobs: int = 0
    pending_jobs: int = 0
    waiting_jobs: int = 0
    running_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    cancelled_jobs: int = 0
    timeout_jobs: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    queue_depth: int = 0
    by_type: dict[JobType, JobTypeMetrics] = field(default_factory=dict)
    oldest_pending_age_seconds: float | None = None
    last_failure_at: datetime | None = None
    last_completion_at: datetime | None = None


class MetricsCollector:
    """Collects and calculates job queue metrics.

    This class is used internally by JobQueue to track statistics
    and provide monitoring data.
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self._completed_durations: list[float] = []
        self._type_durations: dict[JobType, list[float]] = {}
        self._last_failure_at: datetime | None = None
        self._last_completion_at: datetime | None = None
        self._failure_callbacks: list[Callable[[FailedJobAlert], Coroutine[Any, Any, None]]] = []

    def on_job_failed(
        self,
        callback: Callable[[FailedJobAlert], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a callback for job failures.

        Args:
            callback: Async function to call when a job fails.
                     Receives a FailedJobAlert with details.
        """
        self._failure_callbacks.append(callback)
        logger.info("failure_callback_registered", total=len(self._failure_callbacks))

    async def record_completion(self, job: Job) -> None:
        """Record a job completion for metrics.

        Args:
            job: The completed job
        """
        if job.started_at and job.completed_at:
            duration = (job.completed_at - job.started_at).total_seconds()
            self._completed_durations.append(duration)

            if job.type not in self._type_durations:
                self._type_durations[job.type] = []
            self._type_durations[job.type].append(duration)

        self._last_completion_at = datetime.now(timezone.utc)

    async def record_failure(self, job: Job) -> None:
        """Record a job failure and trigger alerts.

        Args:
            job: The failed job
        """
        self._last_failure_at = datetime.now(timezone.utc)

        # Calculate duration
        duration = None
        if job.started_at and job.completed_at:
            duration = (job.completed_at - job.started_at).total_seconds()

        # Create alert
        alert = FailedJobAlert(
            job_id=job.id,
            job_type=job.type,
            error=job.error or "Unknown error",
            failed_at=self._last_failure_at,
            duration_seconds=duration,
            metadata=job.metadata,
        )

        # Trigger callbacks
        for callback in self._failure_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(
                    "failure_callback_error",
                    callback=callback.__name__,
                    error=str(e),
                    exc_info=True,
                )

    def calculate_metrics(self, jobs: dict[str, Job], queue_size: int) -> JobMetrics:
        """Calculate current metrics from job registry.

        Args:
            jobs: Dictionary of all jobs
            queue_size: Current queue depth

        Returns:
            JobMetrics with current statistics
        """
        now = datetime.now(timezone.utc)

        metrics = JobMetrics()
        metrics.total_jobs = len(jobs)
        metrics.queue_depth = queue_size
        metrics.last_failure_at = self._last_failure_at
        metrics.last_completion_at = self._last_completion_at

        oldest_pending_time: datetime | None = None

        for job in jobs.values():
            # Count by status
            if job.status == JobStatus.PENDING:
                metrics.pending_jobs += 1
                if oldest_pending_time is None or job.created_at < oldest_pending_time:
                    oldest_pending_time = job.created_at
            elif job.status == JobStatus.WAITING:
                metrics.waiting_jobs += 1
            elif job.status == JobStatus.RUNNING:
                metrics.running_jobs += 1
            elif job.status == JobStatus.COMPLETED:
                metrics.completed_jobs += 1
            elif job.status == JobStatus.FAILED:
                metrics.failed_jobs += 1
            elif job.status == JobStatus.CANCELLED:
                metrics.cancelled_jobs += 1
            elif job.status == JobStatus.TIMEOUT:
                metrics.timeout_jobs += 1

            # Track per-type metrics
            if job.type not in metrics.by_type:
                metrics.by_type[job.type] = JobTypeMetrics(job_type=job.type)

            type_metrics = metrics.by_type[job.type]
            type_metrics.total_jobs += 1

            if job.status == JobStatus.COMPLETED:
                type_metrics.completed += 1
            elif job.status == JobStatus.FAILED:
                type_metrics.failed += 1
            elif job.status == JobStatus.CANCELLED:
                type_metrics.cancelled += 1
            elif job.status == JobStatus.TIMEOUT:
                type_metrics.timeout += 1

        # Calculate oldest pending age
        if oldest_pending_time:
            metrics.oldest_pending_age_seconds = (now - oldest_pending_time).total_seconds()

        # Calculate success rate
        terminal = metrics.completed_jobs + metrics.failed_jobs + metrics.timeout_jobs
        if terminal > 0:
            metrics.success_rate = metrics.completed_jobs / terminal

        # Calculate average duration
        if self._completed_durations:
            metrics.avg_duration_seconds = sum(self._completed_durations) / len(
                self._completed_durations
            )

        # Calculate per-type durations
        for job_type, durations in self._type_durations.items():
            if job_type in metrics.by_type and durations:
                metrics.by_type[job_type].total_duration_seconds = sum(durations)
                metrics.by_type[job_type].avg_duration_seconds = sum(durations) / len(durations)

        return metrics
