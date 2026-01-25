"""Tests for job queue functionality."""

import asyncio

import pytest

from fuzzbin.tasks import Job, JobQueue, JobStatus, JobType


@pytest.fixture
def queue() -> JobQueue:
    """Create a job queue for testing."""
    return JobQueue(max_workers=1)


async def dummy_handler(job: Job) -> None:
    """Simple handler that completes immediately."""
    await asyncio.sleep(0.05)  # Small delay to simulate work
    job.mark_completed({"status": "success", "message": "Dummy job completed"})


async def slow_handler(job: Job) -> None:
    """Handler that takes time to complete."""
    for i in range(5):
        if job.status == JobStatus.CANCELLED:
            return
        job.update_progress(i + 1, 5, f"Step {i + 1} of 5")
        await asyncio.sleep(0.1)
    job.mark_completed({"steps_completed": 5})


async def failing_handler(job: Job) -> None:
    """Handler that raises an exception."""
    raise ValueError("Simulated failure")


class TestJobModel:
    """Tests for the Job model."""

    def test_job_creation(self):
        """Test creating a new job."""
        job = Job(type=JobType.IMPORT_NFO, metadata={"directory": "/test"})

        assert job.id is not None
        assert job.type == JobType.IMPORT_NFO
        assert job.status == JobStatus.PENDING
        assert job.progress == 0.0
        assert job.metadata == {"directory": "/test"}
        assert job.result is None
        assert job.error is None

    def test_job_update_progress(self):
        """Test updating job progress."""
        job = Job(type=JobType.IMPORT_NFO)

        job.update_progress(5, 10, "Processing file 5...")

        assert job.processed_items == 5
        assert job.total_items == 10
        assert job.progress == 0.5
        assert job.current_step == "Processing file 5..."

    def test_job_mark_running(self):
        """Test marking job as running."""
        job = Job(type=JobType.IMPORT_NFO)
        assert job.started_at is None

        job.mark_running()

        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

    def test_job_mark_completed(self):
        """Test marking job as completed."""
        job = Job(type=JobType.IMPORT_NFO)
        job.mark_running()

        job.mark_completed({"imported": 10})

        assert job.status == JobStatus.COMPLETED
        assert job.result == {"imported": 10}
        assert job.progress == 1.0
        assert job.completed_at is not None

    def test_job_mark_failed(self):
        """Test marking job as failed."""
        job = Job(type=JobType.IMPORT_NFO)
        job.mark_running()

        job.mark_failed("Something went wrong")

        assert job.status == JobStatus.FAILED
        assert job.error == "Something went wrong"
        assert job.completed_at is not None

    def test_job_mark_cancelled(self):
        """Test marking job as cancelled."""
        job = Job(type=JobType.IMPORT_NFO)

        job.mark_cancelled()

        assert job.status == JobStatus.CANCELLED
        assert job.completed_at is not None

    def test_job_is_terminal(self):
        """Test is_terminal property."""
        job = Job(type=JobType.IMPORT_NFO)

        assert not job.is_terminal

        job.mark_completed({})
        assert job.is_terminal

        job2 = Job(type=JobType.IMPORT_NFO)
        job2.mark_failed("error")
        assert job2.is_terminal

        job3 = Job(type=JobType.IMPORT_NFO)
        job3.mark_cancelled()
        assert job3.is_terminal


class TestJobQueue:
    """Tests for the JobQueue class."""

    @pytest.mark.asyncio
    async def test_register_handler(self, queue: JobQueue):
        """Test registering a job handler."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)

        assert JobType.IMPORT_NFO in queue.handlers
        assert queue.handlers[JobType.IMPORT_NFO] == dummy_handler

    @pytest.mark.asyncio
    async def test_submit_job(self, queue: JobQueue):
        """Test submitting a job."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)

        job = Job(type=JobType.IMPORT_NFO, metadata={"test": "data"})
        job_id = await queue.submit(job)

        assert job_id == job.id
        assert job.id in queue.jobs
        assert queue.jobs[job.id].status == JobStatus.PENDING

    @pytest.mark.asyncio
    async def test_submit_unhandled_job_type(self, queue: JobQueue):
        """Test submitting a job with no handler raises error."""
        job = Job(type=JobType.IMPORT_NFO)

        with pytest.raises(ValueError, match="No handler registered"):
            await queue.submit(job)

    @pytest.mark.asyncio
    async def test_get_job(self, queue: JobQueue):
        """Test retrieving a job by ID."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)

        job = Job(type=JobType.IMPORT_NFO)
        await queue.submit(job)

        retrieved = await queue.get_job(job.id)
        assert retrieved == job

        # Non-existent job returns None
        missing = await queue.get_job("non-existent-id")
        assert missing is None

    @pytest.mark.asyncio
    async def test_list_jobs(self, queue: JobQueue):
        """Test listing jobs."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)
        queue.register_handler(JobType.FILE_ORGANIZE, dummy_handler)

        # Submit multiple jobs
        job1 = Job(type=JobType.IMPORT_NFO)
        job2 = Job(type=JobType.FILE_ORGANIZE)
        job3 = Job(type=JobType.IMPORT_NFO)

        await queue.submit(job1)
        await queue.submit(job2)
        await queue.submit(job3)

        # List all
        all_jobs = await queue.list_jobs()
        assert len(all_jobs) == 3

        # List by type
        nfo_jobs = await queue.list_jobs(job_type=JobType.IMPORT_NFO)
        assert len(nfo_jobs) == 2
        assert all(j.type == JobType.IMPORT_NFO for j in nfo_jobs)

        # List with limit
        limited = await queue.list_jobs(limit=2)
        assert len(limited) == 2

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self, queue: JobQueue):
        """Test cancelling a pending job."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)

        job = Job(type=JobType.IMPORT_NFO)
        await queue.submit(job)

        cancelled = await queue.cancel_job(job.id)

        assert cancelled is True
        assert job.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, queue: JobQueue):
        """Test cancelling a non-existent job returns False."""
        cancelled = await queue.cancel_job("non-existent-id")
        assert cancelled is False

    @pytest.mark.asyncio
    async def test_cancel_completed_job(self, queue: JobQueue):
        """Test cancelling an already completed job returns False."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)

        job = Job(type=JobType.IMPORT_NFO)
        job.mark_completed({})
        queue.jobs[job.id] = job

        cancelled = await queue.cancel_job(job.id)
        assert cancelled is False

    @pytest.mark.asyncio
    async def test_job_execution(self, queue: JobQueue):
        """Test that jobs are executed by workers."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)

        job = Job(type=JobType.IMPORT_NFO)
        await queue.submit(job)

        # Start queue and wait for job to complete
        await queue.start()
        await asyncio.sleep(0.2)  # Give time for job to execute
        await queue.stop()

        assert job.status == JobStatus.COMPLETED
        assert job.result == {"status": "success", "message": "Dummy job completed"}

    @pytest.mark.asyncio
    async def test_job_execution_with_progress(self, queue: JobQueue):
        """Test that job progress updates work."""
        queue.register_handler(JobType.IMPORT_NFO, slow_handler)

        job = Job(type=JobType.IMPORT_NFO)
        await queue.submit(job)

        await queue.start()
        await asyncio.sleep(0.7)  # Give time for slow job
        await queue.stop()

        assert job.status == JobStatus.COMPLETED
        assert job.progress == 1.0
        assert job.result == {"steps_completed": 5}

    @pytest.mark.asyncio
    async def test_job_failure(self, queue: JobQueue):
        """Test that job failures are handled."""
        queue.register_handler(JobType.IMPORT_NFO, failing_handler)

        job = Job(type=JobType.IMPORT_NFO)
        await queue.submit(job)

        await queue.start()
        await asyncio.sleep(0.2)
        await queue.stop()

        assert job.status == JobStatus.FAILED
        assert "Simulated failure" in job.error

    @pytest.mark.asyncio
    async def test_queue_start_stop(self, queue: JobQueue):
        """Test starting and stopping the queue."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)

        assert not queue.running
        assert len(queue.workers) == 0

        await queue.start()

        assert queue.running
        assert len(queue.workers) == 1  # max_workers=1

        await queue.stop()

        assert not queue.running
        assert len(queue.workers) == 0


class TestGlobalJobQueue:
    """Tests for global job queue functions."""

    @pytest.mark.asyncio
    async def test_init_and_get_job_queue(self):
        """Test initializing and getting global job queue."""
        from fuzzbin.tasks import get_job_queue, init_job_queue, reset_job_queue

        # Reset any existing queue
        reset_job_queue()

        # Should raise before initialization
        with pytest.raises(RuntimeError, match="not initialized"):
            get_job_queue()

        # Initialize
        queue = init_job_queue(max_workers=3)
        assert queue is not None
        assert queue.max_workers == 3

        # Get should return same instance
        same_queue = get_job_queue()
        assert same_queue is queue

        # Cleanup
        reset_job_queue()


class TestJobTypes:
    """Tests for all job type enumerations."""

    def test_all_job_types_defined(self):
        """Test that all expected job types are defined."""
        expected_types = [
            "import_nfo",
            "import_spotify",
            "download_youtube",
            "file_organize",
            "file_duplicate_resolve",
            "metadata_enrich",
        ]

        for type_value in expected_types:
            job_type = JobType(type_value)
            assert job_type.value == type_value

    def test_job_creation_all_types(self):
        """Test creating jobs with all job types."""
        all_types = [
            JobType.IMPORT_NFO,
            JobType.IMPORT_SPOTIFY,
            JobType.DOWNLOAD_YOUTUBE,
            JobType.FILE_ORGANIZE,
            JobType.FILE_DUPLICATE_RESOLVE,
            JobType.METADATA_ENRICH,
        ]

        for job_type in all_types:
            job = Job(type=job_type, metadata={"test": True})
            assert job.type == job_type
            assert job.status == JobStatus.PENDING


class TestJobHandlerRegistration:
    """Tests for job handler registration."""

    @pytest.mark.asyncio
    async def test_register_all_handlers(self, queue: JobQueue):
        """Test that all handlers can be registered."""
        from fuzzbin.tasks.handlers import register_all_handlers

        register_all_handlers(queue)

        # Check all job types have handlers
        expected_types = [
            JobType.IMPORT_NFO,
            JobType.IMPORT_SPOTIFY,
            JobType.DOWNLOAD_YOUTUBE,
            JobType.FILE_ORGANIZE,
            JobType.FILE_DUPLICATE_RESOLVE,
            JobType.METADATA_ENRICH,
        ]

        for job_type in expected_types:
            assert job_type in queue.handlers, f"Handler missing for {job_type}"

    @pytest.mark.asyncio
    async def test_submit_all_job_types(self, queue: JobQueue):
        """Test that all job types can be submitted after registration."""
        from fuzzbin.tasks.handlers import register_all_handlers

        register_all_handlers(queue)

        # Submit each type (will fail in execution, but submission should work)
        job_metadata_map = {
            JobType.IMPORT_NFO: {"directory": "/tmp/test"},
            JobType.IMPORT_SPOTIFY: {"playlist_id": "test123"},
            JobType.DOWNLOAD_YOUTUBE: {"video_ids": [1, 2, 3]},
            JobType.FILE_ORGANIZE: {"video_ids": [1, 2]},
            JobType.FILE_DUPLICATE_RESOLVE: {"scan_all": True},
            JobType.METADATA_ENRICH: {"video_ids": [1]},
        }

        for job_type, metadata in job_metadata_map.items():
            job = Job(type=job_type, metadata=metadata)
            job_id = await queue.submit(job)
            assert job_id is not None
            assert job.id in queue.jobs


class TestJobPriority:
    """Tests for job priority features."""

    def test_job_priority_default(self):
        """Test that jobs have normal priority by default."""
        from fuzzbin.tasks import JobPriority

        job = Job(type=JobType.IMPORT_NFO)
        assert job.priority == JobPriority.NORMAL

    def test_job_with_custom_priority(self):
        """Test creating a job with custom priority."""
        from fuzzbin.tasks import JobPriority

        job = Job(type=JobType.IMPORT_NFO, priority=JobPriority.HIGH)
        assert job.priority == JobPriority.HIGH

    def test_job_comparison_by_priority(self):
        """Test that jobs compare by priority (higher priority = lower value for heap)."""
        from fuzzbin.tasks import JobPriority

        low_job = Job(type=JobType.IMPORT_NFO, priority=JobPriority.LOW)
        normal_job = Job(type=JobType.IMPORT_NFO, priority=JobPriority.NORMAL)
        high_job = Job(type=JobType.IMPORT_NFO, priority=JobPriority.HIGH)
        critical_job = Job(type=JobType.IMPORT_NFO, priority=JobPriority.CRITICAL)

        # In a min-heap, critical should come first (lowest comparison value)
        assert critical_job < high_job
        assert high_job < normal_job
        assert normal_job < low_job

    @pytest.mark.asyncio
    async def test_priority_queue_ordering(self, queue: JobQueue):
        """Test that higher priority jobs are processed first."""
        from fuzzbin.tasks import JobPriority

        processed_order = []

        async def tracking_handler(job: Job) -> None:
            processed_order.append(job.id)
            job.mark_completed({"priority": job.priority.value})

        queue.register_handler(JobType.IMPORT_NFO, tracking_handler)

        # Submit jobs in opposite order of priority
        low_job = Job(type=JobType.IMPORT_NFO, priority=JobPriority.LOW)
        normal_job = Job(type=JobType.IMPORT_NFO, priority=JobPriority.NORMAL)
        high_job = Job(type=JobType.IMPORT_NFO, priority=JobPriority.HIGH)

        await queue.submit(low_job)
        await queue.submit(normal_job)
        await queue.submit(high_job)

        # Start queue and wait for completion
        await queue.start()
        await asyncio.sleep(0.5)  # Allow processing
        await queue.stop()

        # High priority should be processed first
        assert processed_order[0] == high_job.id
        assert processed_order[1] == normal_job.id
        assert processed_order[2] == low_job.id


class TestJobTimeout:
    """Tests for job timeout features."""

    def test_job_with_timeout(self):
        """Test creating a job with timeout."""
        job = Job(type=JobType.IMPORT_NFO, timeout_seconds=60)
        assert job.timeout_seconds == 60

    def test_job_mark_timeout(self):
        """Test marking a job as timed out."""
        job = Job(type=JobType.IMPORT_NFO, timeout_seconds=10)
        job.mark_running()
        job.mark_timeout()

        assert job.status == JobStatus.TIMEOUT
        assert job.error == "Job exceeded timeout of 10 seconds"
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_job_timeout_in_queue(self, queue: JobQueue):
        """Test that jobs timeout when exceeding their limit."""

        async def slow_handler(job: Job) -> None:
            await asyncio.sleep(5)  # Longer than timeout
            job.mark_completed({})

        queue.register_handler(JobType.IMPORT_NFO, slow_handler)

        job = Job(type=JobType.IMPORT_NFO, timeout_seconds=1)
        await queue.submit(job)

        await queue.start()
        await asyncio.sleep(2)  # Allow timeout to occur
        await queue.stop()

        assert job.status == JobStatus.TIMEOUT
        assert "timeout" in job.error.lower()


class TestJobDependencies:
    """Tests for job dependency features."""

    def test_job_with_dependencies(self):
        """Test creating a job with dependencies."""
        parent_job = Job(type=JobType.IMPORT_NFO)
        child_job = Job(type=JobType.METADATA_ENRICH, depends_on=[parent_job.id])

        assert child_job.depends_on == [parent_job.id]

    def test_job_mark_waiting(self):
        """Test marking a job as waiting for dependencies."""
        job = Job(type=JobType.IMPORT_NFO, depends_on=["some-other-job"])
        job.mark_waiting()

        assert job.status == JobStatus.WAITING

    @pytest.mark.asyncio
    async def test_dependent_job_waits(self, queue: JobQueue):
        """Test that dependent jobs wait for parent to complete."""

        async def simple_handler(job: Job) -> None:
            job.mark_completed({"done": True})

        queue.register_handler(JobType.IMPORT_NFO, simple_handler)
        queue.register_handler(JobType.METADATA_ENRICH, simple_handler)

        parent_job = Job(type=JobType.IMPORT_NFO)
        child_job = Job(type=JobType.METADATA_ENRICH, depends_on=[parent_job.id])

        # Submit parent first
        await queue.submit(parent_job)
        # Submit child - should go to WAITING status
        await queue.submit(child_job)

        # Child should be waiting
        assert child_job.status == JobStatus.WAITING

        await queue.start()
        await asyncio.sleep(0.5)  # Allow processing
        await queue.stop()

        # Both should be completed
        assert parent_job.status == JobStatus.COMPLETED
        assert child_job.status == JobStatus.COMPLETED


class TestJobScheduling:
    """Tests for job scheduling features."""

    def test_job_with_schedule(self):
        """Test creating a scheduled job."""
        job = Job(type=JobType.FILE_ORGANIZE, schedule="0 2 * * *")
        assert job.schedule == "0 2 * * *"

    @pytest.mark.asyncio
    async def test_scheduled_job_submission(self, queue: JobQueue):
        """Test that scheduled jobs go to WAITING status."""
        queue.register_handler(JobType.FILE_ORGANIZE, dummy_handler)

        job = Job(type=JobType.FILE_ORGANIZE, schedule="0 2 * * *")
        await queue.submit(job)

        assert job.status == JobStatus.WAITING
        assert job.next_run_at is not None

    @pytest.mark.asyncio
    async def test_invalid_schedule_raises_error(self, queue: JobQueue):
        """Test that invalid cron expression raises error."""
        queue.register_handler(JobType.FILE_ORGANIZE, dummy_handler)

        job = Job(type=JobType.FILE_ORGANIZE, schedule="invalid cron")

        with pytest.raises(ValueError, match="Invalid cron expression"):
            await queue.submit(job)


class TestCronParser:
    """Tests for cron expression parsing."""

    def test_parse_every_minute(self):
        """Test parsing every-minute cron."""
        from datetime import datetime, timezone

        from fuzzbin.tasks.queue import parse_cron

        now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        next_run = parse_cron("* * * * *", now)

        assert next_run is not None
        assert next_run > now
        assert next_run.minute == 31  # Next minute

    def test_parse_every_hour(self):
        """Test parsing every-hour cron."""
        from datetime import datetime, timezone

        from fuzzbin.tasks.queue import parse_cron

        now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        next_run = parse_cron("0 * * * *", now)

        assert next_run is not None
        assert next_run > now
        assert next_run.minute == 0
        assert next_run.hour >= 11  # At least next hour

    def test_parse_every_15_minutes(self):
        """Test parsing every-15-minutes cron."""
        from datetime import datetime, timezone

        from fuzzbin.tasks.queue import parse_cron

        now = datetime(2024, 1, 15, 10, 7, 0, tzinfo=timezone.utc)
        next_run = parse_cron("*/15 * * * *", now)

        assert next_run is not None
        assert next_run > now
        assert next_run.minute in [0, 15, 30, 45]

    def test_parse_invalid_cron(self):
        """Test parsing invalid cron returns None."""
        from datetime import datetime, timezone

        from fuzzbin.tasks.queue import parse_cron

        now = datetime.now(timezone.utc)

        assert parse_cron("invalid", now) is None
        assert parse_cron("1 2 3", now) is None  # Too few fields
        assert parse_cron("1 2 3 4 5 6", now) is None  # Too many fields


class TestJobMetrics:
    """Tests for job queue metrics and monitoring."""

    @pytest.mark.asyncio
    async def test_get_metrics_empty_queue(self, queue: JobQueue):
        """Test getting metrics from empty queue."""
        metrics = queue.get_metrics()

        assert metrics.total_jobs == 0
        assert metrics.pending_jobs == 0
        assert metrics.running_jobs == 0
        assert metrics.completed_jobs == 0
        assert metrics.failed_jobs == 0
        assert metrics.success_rate == 0.0
        assert metrics.queue_depth == 0

    @pytest.mark.asyncio
    async def test_metrics_after_job_completion(self, queue: JobQueue):
        """Test metrics are updated after job completion."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)

        job = Job(type=JobType.IMPORT_NFO)
        await queue.submit(job)

        await queue.start()
        await asyncio.sleep(0.3)  # Allow job to complete
        await queue.stop()

        metrics = queue.get_metrics()
        assert metrics.total_jobs == 1
        assert metrics.completed_jobs == 1
        assert metrics.success_rate == 1.0
        assert metrics.avg_duration_seconds > 0
        assert metrics.last_completion_at is not None

    @pytest.mark.asyncio
    async def test_metrics_after_job_failure(self, queue: JobQueue):
        """Test metrics are updated after job failure."""
        queue.register_handler(JobType.IMPORT_NFO, failing_handler)

        job = Job(type=JobType.IMPORT_NFO)
        await queue.submit(job)

        await queue.start()
        await asyncio.sleep(0.3)
        await queue.stop()

        metrics = queue.get_metrics()
        assert metrics.total_jobs == 1
        assert metrics.failed_jobs == 1
        assert metrics.success_rate == 0.0
        assert metrics.last_failure_at is not None

    @pytest.mark.asyncio
    async def test_metrics_by_job_type(self, queue: JobQueue):
        """Test per-type metrics are tracked."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)
        queue.register_handler(JobType.FILE_ORGANIZE, dummy_handler)

        # Submit different job types
        await queue.submit(Job(type=JobType.IMPORT_NFO))
        await queue.submit(Job(type=JobType.IMPORT_NFO))
        await queue.submit(Job(type=JobType.FILE_ORGANIZE))

        await queue.start()
        await asyncio.sleep(0.5)
        await queue.stop()

        metrics = queue.get_metrics()
        assert JobType.IMPORT_NFO in metrics.by_type
        assert JobType.FILE_ORGANIZE in metrics.by_type
        assert metrics.by_type[JobType.IMPORT_NFO].completed == 2
        assert metrics.by_type[JobType.FILE_ORGANIZE].completed == 1


class TestFailedJobAlerts:
    """Tests for failed job alert system."""

    @pytest.mark.asyncio
    async def test_failure_callback_triggered(self, queue: JobQueue):
        """Test that failure callback is triggered on job failure."""
        from fuzzbin.tasks import FailedJobAlert

        alerts_received: list[FailedJobAlert] = []

        async def capture_alert(alert: FailedJobAlert) -> None:
            alerts_received.append(alert)

        queue.register_handler(JobType.IMPORT_NFO, failing_handler)
        queue.on_job_failed(capture_alert)

        job = Job(type=JobType.IMPORT_NFO, metadata={"test": "data"})
        await queue.submit(job)

        await queue.start()
        await asyncio.sleep(0.3)
        await queue.stop()

        assert len(alerts_received) == 1
        alert = alerts_received[0]
        assert alert.job_id == job.id
        assert alert.job_type == JobType.IMPORT_NFO
        assert "Simulated failure" in alert.error
        assert alert.metadata == {"test": "data"}

    @pytest.mark.asyncio
    async def test_failure_callback_on_timeout(self, queue: JobQueue):
        """Test that failure callback is triggered on job timeout."""
        from fuzzbin.tasks import FailedJobAlert

        alerts_received: list[FailedJobAlert] = []

        async def capture_alert(alert: FailedJobAlert) -> None:
            alerts_received.append(alert)

        async def very_slow_handler(job: Job) -> None:
            await asyncio.sleep(10)

        queue.register_handler(JobType.IMPORT_NFO, very_slow_handler)
        queue.on_job_failed(capture_alert)

        job = Job(type=JobType.IMPORT_NFO, timeout_seconds=1)
        await queue.submit(job)

        await queue.start()
        await asyncio.sleep(2)
        await queue.stop()

        assert len(alerts_received) == 1
        assert "timeout" in alerts_received[0].error.lower()

    @pytest.mark.asyncio
    async def test_multiple_failure_callbacks(self, queue: JobQueue):
        """Test multiple failure callbacks are all triggered."""
        callback1_count = 0
        callback2_count = 0

        async def callback1(alert) -> None:
            nonlocal callback1_count
            callback1_count += 1

        async def callback2(alert) -> None:
            nonlocal callback2_count
            callback2_count += 1

        queue.register_handler(JobType.IMPORT_NFO, failing_handler)
        queue.on_job_failed(callback1)
        queue.on_job_failed(callback2)

        await queue.submit(Job(type=JobType.IMPORT_NFO))

        await queue.start()
        await asyncio.sleep(0.3)
        await queue.stop()

        assert callback1_count == 1
        assert callback2_count == 1

    @pytest.mark.asyncio
    async def test_failure_callback_exception_doesnt_break_queue(self, queue: JobQueue):
        """Test that exception in callback doesn't break the queue."""

        async def bad_callback(alert) -> None:
            raise RuntimeError("Callback error")

        async def good_callback(alert) -> None:
            pass

        queue.register_handler(JobType.IMPORT_NFO, failing_handler)
        queue.on_job_failed(bad_callback)
        queue.on_job_failed(good_callback)

        await queue.submit(Job(type=JobType.IMPORT_NFO))

        await queue.start()
        await asyncio.sleep(0.3)
        await queue.stop()

        # Queue should still work
        metrics = queue.get_metrics()
        assert metrics.failed_jobs == 1
