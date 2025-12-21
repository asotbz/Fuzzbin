"""Tests for job queue functionality."""

import asyncio

import pytest
import pytest_asyncio

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

    @pytest.mark.asyncio
    async def test_clear_completed(self, queue: JobQueue):
        """Test clearing completed jobs."""
        queue.register_handler(JobType.IMPORT_NFO, dummy_handler)

        # Create some jobs in various states
        job1 = Job(type=JobType.IMPORT_NFO)
        job1.mark_completed({})
        queue.jobs[job1.id] = job1

        job2 = Job(type=JobType.IMPORT_NFO)
        job2.mark_failed("error")
        queue.jobs[job2.id] = job2

        job3 = Job(type=JobType.IMPORT_NFO)  # Still pending
        queue.jobs[job3.id] = job3

        cleared = await queue.clear_completed()

        assert cleared == 2  # Only completed and failed
        assert job1.id not in queue.jobs
        assert job2.id not in queue.jobs
        assert job3.id in queue.jobs  # Pending job remains


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
