"""Async job queue manager."""

import asyncio
import heapq
from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import structlog

from fuzzbin.tasks.metrics import FailedJobAlert, JobMetrics, MetricsCollector
from fuzzbin.tasks.models import Job, JobPriority, JobStatus, JobType

if TYPE_CHECKING:
    from fuzzbin.core.db.repository import VideoRepository
    from fuzzbin.core.event_bus import EventBus

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
    """Database-backed async job queue with worker pool.

    Provides background task execution with:
    - Configurable worker pool size
    - Priority-based job ordering
    - Job timeouts
    - Job dependencies
    - Scheduled jobs (cron-like)
    - Job submission, cancellation, and listing
    - Handler registration per job type
    - Graceful startup and shutdown
    - **Database persistence** for job recovery across restarts

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
        self.jobs: dict[str, Job] = {}  # Active jobs only (pending/waiting/running)
        self.scheduled_templates: dict[
            str, Job
        ] = {}  # Cron job templates (separate from executions)
        self.handlers: dict[JobType, Callable[[Job], Coroutine[Any, Any, None]]] = {}
        self.workers: list[asyncio.Task[None]] = []
        self.scheduler_task: asyncio.Task[None] | None = None
        self.running = False
        self._lock = asyncio.Lock()
        self._metrics = MetricsCollector()
        self._event_bus: "EventBus | None" = None
        self._repository: "VideoRepository | None" = None

    def set_repository(self, repository: "VideoRepository") -> None:
        """Set the repository for database persistence.

        When set, jobs will be persisted to the database and recovered
        on startup. Without a repository, jobs exist only in memory.

        Args:
            repository: VideoRepository instance for job persistence
        """
        self._repository = repository
        logger.info("job_queue_repository_configured")

    def set_event_bus(self, event_bus: "EventBus") -> None:
        """Set the event bus for real-time job updates.

        When set, the queue will emit events for job state changes:
        - job_started: When a job begins execution
        - job_progress: When job.update_progress() is called (debounced)
        - job_completed: When a job completes successfully
        - job_failed: When a job fails with an error
        - job_cancelled: When a job is cancelled
        - job_timeout: When a job exceeds its timeout

        Args:
            event_bus: EventBus instance for broadcasting events
        """
        self._event_bus = event_bus
        logger.info("job_queue_event_bus_configured")

    def _create_progress_callback(
        self, job: Job
    ) -> Callable[[Job, float | None, int | None], None]:
        """Create a progress callback that emits events via the event bus.

        Progress updates are sent over WebSocket in real-time (with 250ms debouncing).
        Database is NOT updated on every progress change - only on major status
        changes (started, completed, failed) to reduce write load.

        Args:
            job: Job to create callback for

        Returns:
            Callback function for job.set_progress_callback()
        """

        def progress_callback(
            job: Job,
            download_speed: float | None,
            eta_seconds: int | None,
        ) -> None:
            if self._event_bus:
                # Schedule the async emit as a task (debounced via event bus)
                asyncio.create_task(
                    self._event_bus.emit_job_progress(job, download_speed, eta_seconds)
                )
            # NOTE: We intentionally don't persist progress to DB on every update.
            # Progress is ephemeral - only final status (completed/failed) matters
            # for persistence. WebSocket handles real-time updates.

        return progress_callback

    def on_job_failed(
        self,
        callback: Callable[[FailedJobAlert], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a callback for job failures (alerts).

        Args:
            callback: Async function to call when a job fails.
                     Receives a FailedJobAlert with job details.

        Example:
            >>> async def alert_on_failure(alert: FailedJobAlert):
            ...     print(f"Job {alert.job_id} failed: {alert.error}")
            ...     await send_notification(alert)
            ...
            >>> queue.on_job_failed(alert_on_failure)
        """
        self._metrics.on_job_failed(callback)

    def get_metrics(self) -> JobMetrics:
        """Get current job queue metrics.

        Returns:
            JobMetrics with success rate, queue depth, etc.

        Example:
            >>> metrics = queue.get_metrics()
            >>> print(f"Success rate: {metrics.success_rate * 100:.1f}%")
            >>> print(f"Queue depth: {metrics.queue_depth}")
        """
        return self._metrics.calculate_metrics(self.jobs, self.queue.qsize())

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

    async def submit(self, job: Job, video_id: int | None = None) -> str:
        """Submit a job to the queue.

        Args:
            job: Job to submit
            video_id: Optional video ID for grouping related jobs

        Returns:
            Job ID

        Raises:
            ValueError: If job type has no registered handler
        """
        if job.type not in self.handlers:
            raise ValueError(f"No handler registered for job type: {job.type.value}")

        async with self._lock:
            # Handle scheduled jobs - store in separate template dict
            if job.schedule:
                next_run = parse_cron(job.schedule, datetime.now(timezone.utc))
                if next_run:
                    job.next_run_at = next_run
                    job.status = JobStatus.WAITING
                    # Store in templates dict, NOT jobs dict
                    self.scheduled_templates[job.id] = job
                    # Persist to database
                    await self._persist_job(job, video_id)
                    logger.info(
                        "scheduled_job_submitted",
                        job_id=job.id,
                        schedule=job.schedule,
                        next_run=next_run.isoformat(),
                    )
                    return job.id
                else:
                    raise ValueError(f"Invalid cron expression: {job.schedule}")

            # Regular jobs go in jobs dict
            self.jobs[job.id] = job

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
                    # Persist to database
                    await self._persist_job(job, video_id)
                    logger.info(
                        "job_waiting_for_dependencies",
                        job_id=job.id,
                        depends_on=job.depends_on,
                        unmet=unmet,
                    )
                    return job.id

            # Persist to database before queuing
            await self._persist_job(job, video_id)

            # Queue immediately
            await self.queue.put(job)
            logger.info(
                "job_submitted",
                job_id=job.id,
                job_type=job.type.value,
                priority=job.priority.value,
                video_id=video_id,
            )
            return job.id

    async def _persist_job(self, job: Job, video_id: int | None = None) -> None:
        """Persist a job to the database.

        Args:
            job: Job to persist
            video_id: Optional video ID for grouping
        """
        if not self._repository:
            return

        try:
            await self._repository.create_job(
                job_id=job.id,
                job_type=job.type.value,
                status=job.status.value,
                priority=job.priority.value,
                metadata=job.metadata,
                video_id=video_id,
                parent_job_id=job.parent_job_id,
                depends_on=job.depends_on if job.depends_on else None,
                timeout_seconds=job.timeout_seconds,
                schedule=job.schedule,
                next_run_at=job.next_run_at.isoformat() if job.next_run_at else None,
            )
        except Exception as e:
            logger.error("job_persist_failed", job_id=job.id, error=str(e))

    async def _update_job_status_db(
        self,
        job: Job,
        error: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Update job status in the database.

        Args:
            job: Job with updated status
            error: Optional error message
            result: Optional result data
        """
        if not self._repository:
            return

        try:
            await self._repository.update_job_status(
                job_id=job.id,
                status=job.status.value,
                error=error,
                result=result,
            )
        except Exception as e:
            logger.error("job_status_persist_failed", job_id=job.id, error=str(e))

    @staticmethod
    def _extract_error_details(error: BaseException) -> dict[str, Any]:
        """Extract stderr/returncode details from exceptions when available."""
        details: dict[str, Any] = {}
        stderr = getattr(error, "stderr", None)
        if stderr:
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            if isinstance(stderr, str):
                cleaned = stderr.strip()
                if cleaned:
                    details["stderr"] = cleaned[:1000]

        returncode = getattr(error, "returncode", None)
        if isinstance(returncode, int):
            details["returncode"] = returncode

        return details

    async def get_job(self, job_id: str) -> Job | None:
        """Get job by ID.

        Checks in-memory registry first (for active jobs), then falls
        back to database for completed/historical jobs.

        Args:
            job_id: Job ID

        Returns:
            Job or None if not found
        """
        # Check in-memory first (for active jobs)
        job = self.jobs.get(job_id)
        if job:
            return job

        # Fall back to database for completed/historical jobs
        if self._repository:
            job_row = await self._repository.get_job(job_id)
            if job_row:
                return self._job_from_db_row(job_row)

        return None

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
        # Persist cancellation to database
        await self._update_job_status_db(job)
        logger.info("job_cancelled", job_id=job_id)
        return True

    async def retry_job(self, job_id: str) -> str | None:
        """Retry a failed job by creating a new job with the same parameters.

        Args:
            job_id: ID of the failed job to retry

        Returns:
            New job ID if retry succeeded, None if job not found or not retriable
        """
        # First check in-memory
        original_job = self.jobs.get(job_id)

        # If not in memory, try to load from database
        if not original_job and self._repository:
            job_row = await self._repository.get_job(job_id)
            if job_row:
                original_job = self._job_from_db_row(job_row)

        if not original_job:
            logger.warning("retry_job_not_found", job_id=job_id)
            return None

        # Only failed jobs can be retried
        if original_job.status not in (JobStatus.FAILED, JobStatus.TIMEOUT, JobStatus.CANCELLED):
            logger.warning(
                "retry_job_not_retriable",
                job_id=job_id,
                status=original_job.status.value,
            )
            return None

        # Create a new job with same parameters
        new_job = Job(
            type=original_job.type,
            priority=original_job.priority,
            metadata=original_job.metadata.copy(),
            timeout_seconds=original_job.timeout_seconds,
            depends_on=original_job.depends_on.copy() if original_job.depends_on else [],
            parent_job_id=original_job.parent_job_id,
        )

        # Get video_id from database if available
        video_id = None
        if self._repository:
            job_row = await self._repository.get_job(job_id)
            if job_row:
                video_id = job_row.get("video_id")

        # Submit the new job
        await self.submit(new_job, video_id=video_id)

        logger.info(
            "job_retried",
            original_job_id=job_id,
            new_job_id=new_job.id,
            job_type=new_job.type.value,
        )

        return new_job.id

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
                # Emit cancelled event
                if self._event_bus:
                    await self._event_bus.emit_job_cancelled(job)
                continue

            job.mark_running()
            # Persist running status
            await self._update_job_status_db(job)

            # Set up progress callback for event bus integration
            if self._event_bus:
                job.set_progress_callback(self._create_progress_callback(job))
                await self._event_bus.emit_job_started(job)

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
                        await asyncio.wait_for(handler(job), timeout=job.timeout_seconds)
                    except asyncio.TimeoutError:
                        job.mark_timeout()
                        # Persist timeout status
                        await self._update_job_status_db(job, error=job.error)
                        # Record timeout as failure for metrics
                        await self._metrics.record_failure(job)
                        # Emit timeout event
                        if self._event_bus:
                            await self._event_bus.emit_job_timeout(job)
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

                # Persist completion status
                await self._update_job_status_db(job, result=job.result)

                # Record completion metrics
                await self._metrics.record_completion(job)

                # Emit completed event
                if self._event_bus:
                    await self._event_bus.emit_job_completed(job)

                logger.info("job_completed", job_id=job.id, status=job.status.value)

                # Check if any waiting jobs can now be queued
                await self._check_waiting_jobs()

            except asyncio.CancelledError:
                job.mark_cancelled()
                # Persist cancellation
                await self._update_job_status_db(job)
                # Emit cancelled event
                if self._event_bus:
                    await self._event_bus.emit_job_cancelled(job)
                logger.warning("job_cancelled_during_execution", job_id=job.id)
                raise

            except Exception as e:
                job.mark_failed(str(e))
                error_details = self._extract_error_details(e)
                if error_details:
                    if job.result is None:
                        job.result = {}
                    if isinstance(job.result, dict):
                        for key, value in error_details.items():
                            job.result.setdefault(key, value)
                # Persist failure status
                await self._update_job_status_db(
                    job,
                    error=str(e),
                    result=job.result if job.result else None,
                )
                # Record failure and trigger alerts
                await self._metrics.record_failure(job)
                # Emit failed event
                if self._event_bus:
                    await self._event_bus.emit_job_failed(job, error=str(e))
                logger.error(
                    "job_failed",
                    job_id=job.id,
                    error=str(e),
                    exc_info=True,
                )

            finally:
                self.queue.task_done()
                # Remove terminal jobs from memory immediately - DB has full record
                # Note: dict.pop with default is thread-safe in CPython, no lock needed
                if job.is_terminal:
                    self.jobs.pop(job.id, None)

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
                        self.jobs.get(dep_id) and self.jobs[dep_id].status == JobStatus.COMPLETED
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
        """Background scheduler for cron-like job execution.

        Iterates over scheduled_templates dict (not jobs dict) to find
        cron jobs that are due. Creates execution instances in jobs dict.
        """
        logger.info("scheduler_started")

        while self.running:
            try:
                now = datetime.now(timezone.utc)

                async with self._lock:
                    # Iterate over scheduled templates, not jobs
                    for job in list(self.scheduled_templates.values()):
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

    async def _recover_jobs_from_database(self) -> None:
        """Recover jobs from database on startup.

        - Mark any RUNNING jobs as FAILED (server restarted)
        - Load PENDING/WAITING jobs back into memory and queue
        """
        if not self._repository:
            logger.debug("job_recovery_skipped_no_repository")
            return

        try:
            # Mark running jobs as failed (server was restarted)
            running_jobs = await self._repository.get_running_jobs()
            for job_row in running_jobs:
                await self._repository.update_job_status(
                    job_id=job_row["id"],
                    status="failed",
                    error="Server restarted — retry manually",
                )
                logger.warning(
                    "job_marked_failed_on_restart",
                    job_id=job_row["id"],
                    job_type=job_row["type"],
                )

            # Load pending/waiting jobs
            pending_jobs = await self._repository.get_pending_jobs()
            for job_row in pending_jobs:
                job = self._job_from_db_row(job_row)
                self.jobs[job.id] = job

                # Only queue pending jobs (waiting jobs need dependencies/schedule)
                if job.status == JobStatus.PENDING:
                    await self.queue.put(job)

            logger.info(
                "jobs_recovered_from_database",
                failed_running=len(running_jobs),
                pending_loaded=len(pending_jobs),
            )

        except Exception as e:
            logger.error("job_recovery_failed", error=str(e), exc_info=True)

    def _job_from_db_row(self, row: dict) -> Job:
        """Reconstruct a Job object from a database row.

        Args:
            row: Database row dict with deserialized JSON fields

        Returns:
            Job instance
        """
        # Parse datetime strings
        created_at = (
            datetime.fromisoformat(row["created_at"])
            if row.get("created_at")
            else datetime.now(timezone.utc)
        )
        started_at = datetime.fromisoformat(row["started_at"]) if row.get("started_at") else None
        completed_at = (
            datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None
        )
        next_run_at = datetime.fromisoformat(row["next_run_at"]) if row.get("next_run_at") else None

        return Job(
            id=row["id"],
            type=JobType(row["type"]),
            status=JobStatus(row["status"]),
            priority=JobPriority(row["priority"]),
            progress=row.get("progress", 0.0),
            current_step=row.get("current_step", "Initializing..."),
            total_items=row.get("total_items", 0),
            processed_items=row.get("processed_items", 0),
            result=row.get("result"),
            error=row.get("error"),
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            metadata=row.get("metadata", {}),
            timeout_seconds=row.get("timeout_seconds"),
            depends_on=row.get("depends_on", []),
            parent_job_id=row.get("parent_job_id"),
            schedule=row.get("schedule"),
            next_run_at=next_run_at,
        )

    async def start(self) -> None:
        """Start the job queue workers and scheduler.

        On startup, recovers jobs from the database:
        - RUNNING jobs are marked as FAILED (server restarted)
        - PENDING/WAITING jobs are reloaded into memory and queue
        """
        if self.running:
            logger.warning("job_queue_already_running")
            return

        # Recover jobs from database before starting workers
        await self._recover_jobs_from_database()

        self.running = True
        self.workers = [asyncio.create_task(self._worker(i)) for i in range(self.max_workers)]
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
