"""Background task processing.

This module provides async job queue functionality for long-running operations
like NFO imports, file organization, and metadata enrichment.

Example:
    >>> from fuzzbin.tasks import Job, JobType, init_job_queue, get_job_queue
    >>>
    >>> # Initialize queue (typically done in app startup)
    >>> queue = init_job_queue(max_workers=2)
    >>> await queue.start()
    >>>
    >>> # Submit a job
    >>> job = Job(type=JobType.IMPORT_NFO, metadata={"directory": "/path/to/nfos"})
    >>> job_id = await queue.submit(job)
    >>>
    >>> # Check job status
    >>> job = await queue.get_job(job_id)
    >>> print(f"Progress: {job.progress * 100:.0f}%")
"""

from fuzzbin.tasks.models import Job, JobStatus, JobType
from fuzzbin.tasks.queue import (
    JobQueue,
    get_job_queue,
    init_job_queue,
    reset_job_queue,
)

__all__ = [
    "Job",
    "JobStatus",
    "JobType",
    "JobQueue",
    "get_job_queue",
    "init_job_queue",
    "reset_job_queue",
]
