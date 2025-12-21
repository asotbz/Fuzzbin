"""Async job queue manager."""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from fuzzbin.tasks.models import Job, JobStatus, JobType

logger = structlog.get_logger(__name__)


class JobQueue:
    """In-memory async job queue with worker pool.

    Provides background task execution with:
    - Configurable worker pool size
    - Job submission, cancellation, and listing
    - Handler registration per job type
    - Graceful startup and shutdown

    Example:
        >>> queue = JobQueue(max_workers=2)
        >>> queue.register_handler(JobType.IMPORT_NFO, handle_nfo_import)
        >>> await queue.start()
        >>> job = Job(type=JobType.IMPORT_NFO, metadata={"directory": "/path"})
        >>> job_id = await queue.submit(job)
        >>> # ... later ...
        >>> await queue.stop()
    """

    def __init__(self, max_workers: int = 2):
        """Initialize job queue.

        Args:
            max_workers: Maximum concurrent workers (default: 2)
        """
        self.max_workers = max_workers
        self.queue: asyncio.Queue[Job] = asyncio.Queue()
        self.jobs: dict[str, Job] = {}  # Job registry
        self.handlers: dict[JobType, Callable[[Job], Coroutine[Any, Any, None]]] = {}
        self.workers: list[asyncio.Task[None]] = []
        self.running = False
        self._lock = asyncio.Lock()

    def register_handler(
        self,
        job_type: JobType,
        handler: Callable[[Job], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a job handler.

        Args:
            job_type: Job type to handle
            handler: Async function to process the job
        """
        self.handlers[job_type] = handler
        logger.info("job_handler_registered", job_type=job_type.value)

    async def submit(self, job: Job) -> str:
        """Submit a job to the queue.

        Args:
            job: Job to submit

        Returns:
            Job ID

        Raises:
            ValueError: If job type has no registered handler
        """
        if job.type not in self.handlers:
            raise ValueError(f"No handler registered for job type: {job.type.value}")

        async with self._lock:
            self.jobs[job.id] = job
            await self.queue.put(job)
            logger.info("job_submitted", job_id=job.id, job_type=job.type.value)
            return job.id

    async def get_job(self, job_id: str) -> Job | None:
        """Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job or None if not found
        """
        return self.jobs.get(job_id)

    async def list_jobs(
        self,
        status: JobStatus | None = None,
        job_type: JobType | None = None,
        limit: int = 100,
    ) -> list[Job]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status (optional)
            job_type: Filter by job type (optional)
            limit: Maximum number of jobs to return

        Returns:
            List of jobs sorted by created_at descending
        """
        jobs = list(self.jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        if job_type:
            jobs = [j for j in jobs if j.type == job_type]

        # Sort by created_at descending (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job.

        Note: Cancellation is cooperative. Running jobs should check
        job.status periodically and exit gracefully when cancelled.

        Args:
            job_id: Job ID

        Returns:
            True if cancelled, False if job not found or already terminal
        """
        job = await self.get_job(job_id)
        if not job:
            return False

        if job.is_terminal:
            return False

        job.mark_cancelled()
        logger.info("job_cancelled", job_id=job_id)
        return True

    async def clear_completed(self, max_age_seconds: int | None = None) -> int:
        """Clear completed/failed/cancelled jobs from registry.

        Args:
            max_age_seconds: Only clear jobs older than this (optional)

        Returns:
            Number of jobs cleared
        """
        from datetime import datetime, timezone

        async with self._lock:
            now = datetime.now(timezone.utc)
            to_remove = []

            for job_id, job in self.jobs.items():
                if not job.is_terminal:
                    continue

                if max_age_seconds is not None and job.completed_at:
                    age = (now - job.completed_at).total_seconds()
                    if age < max_age_seconds:
                        continue

                to_remove.append(job_id)

            for job_id in to_remove:
                del self.jobs[job_id]

            if to_remove:
                logger.info("jobs_cleared", count=len(to_remove))

            return len(to_remove)

    async def _worker(self, worker_id: int) -> None:
        """Background worker coroutine.

        Args:
            worker_id: Worker identifier for logging
        """
        logger.info("worker_started", worker_id=worker_id)

        while self.running:
            try:
                # Wait for job with timeout to allow graceful shutdown
                job = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            # Check if job was cancelled while in queue
            if job.status == JobStatus.CANCELLED:
                self.queue.task_done()
                continue

            job.mark_running()
            logger.info(
                "job_started",
                job_id=job.id,
                job_type=job.type.value,
                worker_id=worker_id,
            )

            try:
                handler = self.handlers[job.type]
                await handler(job)

                # Only mark completed if not already terminal (handler may have
                # marked it completed with custom result, or it was cancelled)
                if job.status == JobStatus.RUNNING:
                    job.mark_completed({"status": "success"})

                logger.info("job_completed", job_id=job.id, status=job.status.value)

            except asyncio.CancelledError:
                job.mark_cancelled()
                logger.warning("job_cancelled_during_execution", job_id=job.id)
                raise

            except Exception as e:
                job.mark_failed(str(e))
                logger.error(
                    "job_failed",
                    job_id=job.id,
                    error=str(e),
                    exc_info=True,
                )

            finally:
                self.queue.task_done()

        logger.info("worker_stopped", worker_id=worker_id)

    async def start(self) -> None:
        """Start the job queue workers."""
        if self.running:
            logger.warning("job_queue_already_running")
            return

        self.running = True
        self.workers = [
            asyncio.create_task(self._worker(i)) for i in range(self.max_workers)
        ]
        logger.info("job_queue_started", max_workers=self.max_workers)

    async def stop(self) -> None:
        """Stop the job queue workers gracefully."""
        if not self.running:
            return

        logger.info("job_queue_stopping")
        self.running = False

        # Wait for workers to finish current jobs
        for worker in self.workers:
            worker.cancel()

        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        logger.info("job_queue_stopped")

    async def wait_until_empty(self) -> None:
        """Wait until all queued jobs are processed."""
        await self.queue.join()


# Global job queue instance
_job_queue: JobQueue | None = None


def get_job_queue() -> JobQueue:
    """Get the global job queue instance.

    Returns:
        JobQueue instance

    Raises:
        RuntimeError: If job queue not initialized
    """
    if _job_queue is None:
        raise RuntimeError("Job queue not initialized. Call init_job_queue() first.")
    return _job_queue


def init_job_queue(max_workers: int = 2) -> JobQueue:
    """Initialize the global job queue.

    Args:
        max_workers: Maximum concurrent workers

    Returns:
        JobQueue instance
    """
    global _job_queue
    _job_queue = JobQueue(max_workers=max_workers)
    logger.info("job_queue_initialized", max_workers=max_workers)
    return _job_queue


def reset_job_queue() -> None:
    """Reset the global job queue (for testing)."""
    global _job_queue
    _job_queue = None
