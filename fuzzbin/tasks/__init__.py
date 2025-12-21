"""Background task processing.

This module provides async job queue functionality for long-running operations
like NFO imports, file organization, and metadata enrichment.

Example:
    >>> from fuzzbin.tasks import Job, JobType, JobPriority, init_job_queue, get_job_queue
    >>>
    >>> # Initialize queue (typically done in app startup)
    >>> queue = init_job_queue(max_workers=2)
    >>> await queue.start()
    >>>
    >>> # Submit a high-priority job with timeout
    >>> job = Job(
    ...     type=JobType.IMPORT_NFO,
    ...     metadata={"directory": "/path/to/nfos"},
    ...     priority=JobPriority.HIGH,
    ...     timeout_seconds=300,
    ... )
    >>> job_id = await queue.submit(job)
    >>>
    >>> # Submit a job with dependencies
    >>> job_a = Job(type=JobType.IMPORT_NFO, metadata={"directory": "/path"})
    >>> job_b = Job(type=JobType.METADATA_ENRICH, depends_on=[job_a.id])
    >>> await queue.submit(job_a)
    >>> await queue.submit(job_b)  # Will wait for job_a to complete
    >>>
    >>> # Submit a scheduled job (runs daily at 2am)
    >>> job = Job(type=JobType.FILE_ORGANIZE, schedule="0 2 * * *")
    >>> await queue.submit(job)
    >>>
    >>> # Get metrics
    >>> metrics = queue.get_metrics()
    >>> print(f"Success rate: {metrics.success_rate * 100:.1f}%")
    >>> print(f"Queue depth: {metrics.queue_depth}")
    >>>
    >>> # Register failure alert
    >>> async def on_failure(alert):
    ...     print(f"Job {alert.job_id} failed: {alert.error}")
    >>> queue.on_job_failed(on_failure)
    >>>
    >>> # Check job status
    >>> job = await queue.get_job(job_id)
    >>> print(f"Progress: {job.progress * 100:.0f}%")
"""

from fuzzbin.tasks.metrics import FailedJobAlert, JobMetrics, JobTypeMetrics
from fuzzbin.tasks.models import Job, JobPriority, JobStatus, JobType
from fuzzbin.tasks.queue import (
    JobQueue,
    get_job_queue,
    init_job_queue,
    reset_job_queue,
)

__all__ = [
    "FailedJobAlert",
    "Job",
    "JobMetrics",
    "JobPriority",
    "JobQueue",
    "JobStatus",
    "JobType",
    "JobTypeMetrics",
    "get_job_queue",
    "init_job_queue",
    "reset_job_queue",
]
