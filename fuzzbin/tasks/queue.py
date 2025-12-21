"""Async job queue manager."""

import asyncio
import heapq
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import Any

import structlog

from fuzzbin.tasks.models import Job, JobPriority, JobStatus, JobType

logger = structlog.get_logger(__name__)


def parse_cron(cron_expr: str, from_time: datetime) -> datetime | None:
    """Parse a cron expression and return the next run time.

    Supports simplified cron format: "minute hour day month weekday"
    Special values: * (any), */N (every N), specific values

    Args:
        cron_expr: Cron expression string
        from_time: Calculate next run after this time

    Returns:
        Next run datetime, or None if invalid expression

    Examples:
        "0 * * * *" - Every hour at minute 0
        "*/15 * * * *" - Every 15 minutes
        "0 2 * * *" - Daily at 2:00 AM
        "0 0 * * 0" - Weekly on Sunday at midnight
    """
    from datetime import timedelta

    try:
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return None

        minute_spec, hour_spec, day_spec, month_spec, weekday_spec = parts

        def parse_field(spec: str, min_val: int, max_val: int) -> list[int]:
            """Parse a cron field into list of valid values."""
            if spec == "*":
                return list(range(min_val, max_val + 1))
            if spec.startswith("*/"):
                step = int(spec[2:])
                return list(range(min_val, max_val + 1, step))
            if "," in spec:
                return [int(v) for v in spec.split(",")]
            return [int(spec)]

        valid_minutes = parse_field(minute_spec, 0, 59)
        valid_hours = parse_field(hour_spec, 0, 23)
        valid_days = parse_field(day_spec, 1, 31)
        valid_months = parse_field(month_spec, 1, 12)
        # Cron weekday: 0=Sunday, Python weekday(): 0=Monday
        # Convert cron weekdays to Python weekdays
        cron_weekdays = parse_field(weekday_spec, 0, 6)
        # Convert: cron 0 (Sun) -> python 6, cron 1 (Mon) -> python 0, etc.
        valid_weekdays = [(w - 1) % 7 for w in cron_weekdays]

        # Find next valid time - start from next minute
        candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)
        candidate = candidate.replace(tzinfo=timezone.utc)

        # Search up to 1 year ahead
        for _ in range(525600):  # Max minutes in a year
            if (
                candidate.minute in valid_minutes
                and candidate.hour in valid_hours
                and candidate.day in valid_days
                and candidate.month in valid_months
                and candidate.weekday() in valid_weekdays
            ):
                return candidate

            # Move to next minute
            candidate = candidate + timedelta(minutes=1)

        return None

    except (ValueError, IndexError):
        return None


class PriorityJobQueue:
    """Priority queue wrapper for jobs.

    Uses a heap to maintain priority ordering where higher priority
    jobs are dequeued first.
    """

    def __init__(self) -> None:
        self._heap: list[Job] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()

    async def put(self, job: Job) -> None:
        """Add a job to the priority queue."""
        async with self._lock:
            heapq.heappush(self._heap, job)
            self._not_empty.set()

    async def get(self, timeout: float = 1.0) -> Job | None:
        """Get the highest priority job.

        Args:
            timeout: Maximum time to wait for a job

        Returns:
            Job or None if timeout
        """
        try:
            await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

        async with self._lock:
            if not self._heap:
                self._not_empty.clear()
                return None

            job = heapq.heappop(self._heap)
            if not self._heap:
                self._not_empty.clear()
            return job

    def task_done(self) -> None:
        """Mark a job as done (compatibility with asyncio.Queue)."""
        pass

    async def join(self) -> None:
        """Wait until queue is empty."""
        while True:
            async with self._lock:
                if not self._heap:
                    return
            await asyncio.sleep(0.1)

    def qsize(self) -> int:
        """Return approximate queue size."""
        return len(self._heap)


class JobQueue:
    """In-memory async job queue with worker pool.

    Provides background task execution with:
    - Configurable worker pool size
    - Priority-based job ordering
    - Job timeouts
    - Job dependencies
    - Scheduled jobs (cron-like)
    - Job submission, cancellation, and listing
    - Handler registration per job type
    - Graceful startup and shutdown

    Example:
        >>> queue = JobQueue(max_workers=2)
        >>> queue.register_handler(JobType.IMPORT_NFO, handle_nfo_import)
        >>> await queue.start()
        >>>
        >>> # Submit with priority
        >>> job = Job(type=JobType.IMPORT_NFO, priority=JobPriority.HIGH)
        >>> await queue.submit(job)
        >>>
        >>> # Submit with timeout
        >>> job = Job(type=JobType.DOWNLOAD_YOUTUBE, timeout_seconds=300)
        >>> await queue.submit(job)
        >>>
        >>> # Submit with dependencies
        >>> job_a = Job(type=JobType.IMPORT_NFO)
        >>> job_b = Job(type=JobType.METADATA_ENRICH, depends_on=[job_a.id])
        >>> await queue.submit(job_a)
        >>> await queue.submit(job_b)  # Will wait for job_a
        >>>
        >>> # Submit scheduled job
        >>> job = Job(type=JobType.FILE_ORGANIZE, schedule="0 2 * * *")  # Daily at 2am
        >>> await queue.submit(job)
    """

    def __init__(self, max_workers: int = 2):
        """Initialize job queue.

        Args:
            max_workers: Maximum concurrent workers (default: 2)
        """
        self.max_workers = max_workers
        self.queue = PriorityJobQueue()
        self.jobs: dict[str, Job] = {}  # Job registry
        self.handlers: dict[JobType, Callable[[Job], Coroutine[Any, Any, None]]] = {}
        self.workers: list[asyncio.Task[None]] = []
        self.scheduler_task: asyncio.Task[None] | None = None
        self.dependency_task: asyncio.Task[None] | None = None
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

            # Handle scheduled jobs
            if job.schedule:
                next_run = parse_cron(job.schedule, datetime.now(timezone.utc))
                if next_run:
                    job.next_run_at = next_run
                    job.status = JobStatus.WAITING
                    logger.info(
                        "scheduled_job_submitted",
                        job_id=job.id,
                        schedule=job.schedule,
                        next_run=next_run.isoformat(),
                    )
                    return job.id
                else:
                    raise ValueError(f"Invalid cron expression: {job.schedule}")

            # Handle jobs with dependencies
            if job.depends_on:
                unmet = [
                    dep_id
                    for dep_id in job.depends_on
                    if dep_id not in self.jobs
                    or not self.jobs[dep_id].status == JobStatus.COMPLETED
                ]
                if unmet:
                    job.status = JobStatus.WAITING
                    logger.info(
                        "job_waiting_for_dependencies",
                        job_id=job.id,
                        depends_on=job.depends_on,
                        unmet=unmet,
                    )
                    return job.id

            # Queue immediately
            await self.queue.put(job)
            logger.info(
                "job_submitted",
                job_id=job.id,
                job_type=job.type.value,
                priority=job.priority.value,
            )
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
            List of jobs sorted by priority then created_at
        """
        jobs = list(self.jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        if job_type:
            jobs = [j for j in jobs if j.type == job_type]

        # Sort by priority (high first) then by created_at (oldest first)
        jobs.sort(key=lambda j: (-j.priority.value, j.created_at))
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
            job = await self.queue.get(timeout=1.0)
            if job is None:
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
                priority=job.priority.value,
            )

            try:
                handler = self.handlers[job.type]

                # Apply timeout if specified
                if job.timeout_seconds:
                    try:
                        await asyncio.wait_for(
                            handler(job), timeout=job.timeout_seconds
                        )
                    except asyncio.TimeoutError:
                        job.mark_timeout()
                        logger.warning(
                            "job_timeout",
                            job_id=job.id,
                            timeout_seconds=job.timeout_seconds,
                        )
                        continue
                else:
                    await handler(job)

                # Only mark completed if not already terminal (handler may have
                # marked it completed with custom result, or it was cancelled)
                if job.status == JobStatus.RUNNING:
                    job.mark_completed({"status": "success"})

                logger.info("job_completed", job_id=job.id, status=job.status.value)

                # Check if any waiting jobs can now be queued
                await self._check_waiting_jobs()

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

    async def _check_waiting_jobs(self) -> None:
        """Check waiting jobs and queue those with met dependencies."""
        async with self._lock:
            for job in list(self.jobs.values()):
                if job.status != JobStatus.WAITING:
                    continue

                # Skip scheduled jobs (handled by scheduler)
                if job.schedule and job.next_run_at:
                    continue

                # Check dependencies
                if job.depends_on:
                    all_completed = all(
                        self.jobs.get(dep_id)
                        and self.jobs[dep_id].status == JobStatus.COMPLETED
                        for dep_id in job.depends_on
                    )

                    if all_completed:
                        job.status = JobStatus.PENDING
                        await self.queue.put(job)
                        logger.info(
                            "job_dependencies_met",
                            job_id=job.id,
                            depends_on=job.depends_on,
                        )

    async def _scheduler(self) -> None:
        """Background scheduler for cron-like job execution."""
        logger.info("scheduler_started")

        while self.running:
            try:
                now = datetime.now(timezone.utc)

                async with self._lock:
                    for job in list(self.jobs.values()):
                        if job.status != JobStatus.WAITING:
                            continue

                        if not job.schedule or not job.next_run_at:
                            continue

                        if now >= job.next_run_at:
                            # Time to run - create a new execution instance
                            # Clone job for execution, keep original for rescheduling
                            execution_job = Job(
                                type=job.type,
                                metadata=job.metadata.copy(),
                                priority=job.priority,
                                timeout_seconds=job.timeout_seconds,
                            )
                            self.jobs[execution_job.id] = execution_job
                            await self.queue.put(execution_job)

                            # Calculate next run time
                            next_run = parse_cron(job.schedule, now)
                            if next_run:
                                job.next_run_at = next_run
                                logger.info(
                                    "scheduled_job_queued",
                                    original_job_id=job.id,
                                    execution_job_id=execution_job.id,
                                    next_run=next_run.isoformat(),
                                )
                            else:
                                # Invalid schedule, mark as failed
                                job.mark_failed("Invalid cron schedule")

                await asyncio.sleep(1)  # Check every second

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("scheduler_error", error=str(e), exc_info=True)
                await asyncio.sleep(5)

        logger.info("scheduler_stopped")

    async def start(self) -> None:
        """Start the job queue workers and scheduler."""
        if self.running:
            logger.warning("job_queue_already_running")
            return

        self.running = True
        self.workers = [
            asyncio.create_task(self._worker(i)) for i in range(self.max_workers)
        ]
        self.scheduler_task = asyncio.create_task(self._scheduler())
        logger.info("job_queue_started", max_workers=self.max_workers)

    async def stop(self) -> None:
        """Stop the job queue workers and scheduler gracefully."""
        if not self.running:
            return

        logger.info("job_queue_stopping")
        self.running = False

        # Cancel scheduler
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
            self.scheduler_task = None

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
