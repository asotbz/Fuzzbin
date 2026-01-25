"""Tests for the async event bus with debounced progress updates."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from fuzzbin.core.event_bus import (
    PROGRESS_DEBOUNCE_INTERVAL,
    DebouncedProgress,
    EventBus,
    get_event_bus,
    init_event_bus,
    reset_event_bus,
)
from fuzzbin.tasks.models import Job, JobPriority, JobType


@pytest.fixture
def event_bus() -> EventBus:
    """Create a fresh event bus for each test."""
    return EventBus()


@pytest.fixture
def mock_broadcast() -> AsyncMock:
    """Create a mock broadcast function."""
    return AsyncMock()


@pytest.fixture
def event_bus_with_broadcast(event_bus: EventBus, mock_broadcast: AsyncMock) -> EventBus:
    """Create an event bus with broadcast function configured."""
    event_bus.set_broadcast_function(mock_broadcast)
    return event_bus


@pytest.fixture
def sample_job() -> Job:
    """Create a sample job for testing."""
    job = Job(
        type=JobType.DOWNLOAD_YOUTUBE,
        metadata={"url": "https://youtube.com/watch?v=test"},
    )
    job.mark_running()
    return job


@pytest.fixture(autouse=True)
def reset_global_event_bus():
    """Reset global event bus before and after each test."""
    reset_event_bus()
    yield
    reset_event_bus()


class TestDebouncedProgress:
    """Tests for DebouncedProgress dataclass."""

    def test_creation_with_defaults(self):
        """Test creating DebouncedProgress with default values."""
        debounced = DebouncedProgress(
            job_id="test-job-123",
            progress=0.5,
            current_step="Downloading",
            processed_items=50,
            total_items=100,
            job_type="youtube_download",
        )

        assert debounced.job_id == "test-job-123"
        assert debounced.progress == 0.5
        assert debounced.current_step == "Downloading"
        assert debounced.processed_items == 50
        assert debounced.total_items == 100
        assert debounced.job_type == "youtube_download"
        assert debounced.download_speed is None
        assert debounced.eta_seconds is None
        assert debounced.flush_task is None
        assert isinstance(debounced.last_update, datetime)

    def test_creation_with_download_fields(self):
        """Test creating DebouncedProgress with download-specific fields."""
        debounced = DebouncedProgress(
            job_id="test-job-123",
            progress=0.75,
            current_step="Downloading video",
            processed_items=75,
            total_items=100,
            job_type="youtube_download",
            download_speed=5.5,
            eta_seconds=30,
        )

        assert debounced.download_speed == 5.5
        assert debounced.eta_seconds == 30


class TestEventBusInitialization:
    """Tests for EventBus initialization and configuration."""

    def test_initialization(self, event_bus: EventBus):
        """Test event bus initializes with empty state."""
        assert event_bus._pending_progress == {}
        assert event_bus._broadcast_fn is None
        assert event_bus._started is False

    def test_set_broadcast_function(self, event_bus: EventBus, mock_broadcast: AsyncMock):
        """Test setting the broadcast function."""
        event_bus.set_broadcast_function(mock_broadcast)

        assert event_bus._broadcast_fn is mock_broadcast
        assert event_bus._started is True


class TestEventCreation:
    """Tests for event dictionary creation."""

    def test_create_event_structure(self, event_bus: EventBus):
        """Test event dictionary has correct structure."""
        event = event_bus._create_event(
            "job_progress",
            {"job_id": "test-123", "progress": 0.5},
        )

        assert event["event_type"] == "job_progress"
        assert "timestamp" in event
        assert event["payload"] == {"job_id": "test-123", "progress": 0.5}

    def test_create_event_timestamp_is_utc(self, event_bus: EventBus):
        """Test event timestamp is in ISO format."""
        event = event_bus._create_event("test_event", {})

        # Should be parseable as ISO datetime
        timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        assert timestamp.tzinfo is not None


class TestBroadcast:
    """Tests for internal broadcast functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_without_function(self, event_bus: EventBus):
        """Test broadcast does nothing when no function is set."""
        # Should not raise
        await event_bus._broadcast({"event_type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_calls_function(
        self, event_bus_with_broadcast: EventBus, mock_broadcast: AsyncMock
    ):
        """Test broadcast calls the configured function."""
        event = {"event_type": "test", "payload": {}}
        await event_bus_with_broadcast._broadcast(event)

        mock_broadcast.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_broadcast_handles_errors(
        self, event_bus_with_broadcast: EventBus, mock_broadcast: AsyncMock
    ):
        """Test broadcast handles exceptions gracefully."""
        mock_broadcast.side_effect = Exception("Network error")

        # Should not raise
        await event_bus_with_broadcast._broadcast({"event_type": "test"})


class TestJobStartedEvent:
    """Tests for job started event emission."""

    @pytest.mark.asyncio
    async def test_emit_job_started(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test emitting job started event."""
        await event_bus_with_broadcast.emit_job_started(sample_job)

        mock_broadcast.assert_called_once()
        event = mock_broadcast.call_args[0][0]

        assert event["event_type"] == "job_started"
        assert event["payload"]["job_id"] == sample_job.id
        assert event["payload"]["job_type"] == "download_youtube"
        assert event["payload"]["priority"] == JobPriority.NORMAL.value
        assert event["payload"]["metadata"] == sample_job.metadata


class TestJobProgressEvent:
    """Tests for job progress event emission with debouncing."""

    @pytest.mark.asyncio
    async def test_emit_job_progress_creates_pending(
        self, event_bus_with_broadcast: EventBus, sample_job: Job
    ):
        """Test emitting progress creates pending entry."""
        sample_job.update_progress(10, 100, "Processing")

        await event_bus_with_broadcast.emit_job_progress(sample_job)

        assert sample_job.id in event_bus_with_broadcast._pending_progress
        pending = event_bus_with_broadcast._pending_progress[sample_job.id]
        assert pending.progress == 0.1
        assert pending.current_step == "Processing"

    @pytest.mark.asyncio
    async def test_emit_job_progress_updates_pending(
        self, event_bus_with_broadcast: EventBus, sample_job: Job
    ):
        """Test rapid progress updates update pending entry without creating new task."""
        sample_job.update_progress(10, 100, "Step 1")
        await event_bus_with_broadcast.emit_job_progress(sample_job)

        first_task = event_bus_with_broadcast._pending_progress[sample_job.id].flush_task

        sample_job.update_progress(20, 100, "Step 2")
        await event_bus_with_broadcast.emit_job_progress(sample_job)

        # Same flush task should be reused
        pending = event_bus_with_broadcast._pending_progress[sample_job.id]
        assert pending.flush_task is first_task
        assert pending.progress == 0.2
        assert pending.current_step == "Step 2"

    @pytest.mark.asyncio
    async def test_emit_job_progress_with_download_fields(
        self, event_bus_with_broadcast: EventBus, sample_job: Job
    ):
        """Test progress with download-specific fields."""
        sample_job.update_progress(50, 100, "Downloading")

        await event_bus_with_broadcast.emit_job_progress(
            sample_job,
            download_speed=10.5,
            eta_seconds=45,
        )

        pending = event_bus_with_broadcast._pending_progress[sample_job.id]
        assert pending.download_speed == 10.5
        assert pending.eta_seconds == 45

    @pytest.mark.asyncio
    async def test_emit_job_progress_debounce_flushes(
        self, event_bus_with_broadcast: EventBus, mock_broadcast: AsyncMock, sample_job: Job
    ):
        """Test progress is flushed after debounce interval."""
        sample_job.update_progress(50, 100, "Processing")

        await event_bus_with_broadcast.emit_job_progress(sample_job)

        # Not yet broadcast
        assert mock_broadcast.call_count == 0

        # Wait for debounce
        await asyncio.sleep(PROGRESS_DEBOUNCE_INTERVAL + 0.1)

        # Now should be broadcast
        assert mock_broadcast.call_count == 1
        event = mock_broadcast.call_args[0][0]
        assert event["event_type"] == "job_progress"
        assert event["payload"]["progress"] == 0.5

    @pytest.mark.asyncio
    async def test_emit_job_progress_batches_rapid_updates(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test rapid progress updates are batched into single broadcast."""
        # Rapid updates
        for i in range(1, 11):
            sample_job.update_progress(i * 10, 100, f"Step {i}")
            await event_bus_with_broadcast.emit_job_progress(sample_job)
            await asyncio.sleep(0.01)  # Small delay but within debounce window

        # Wait for debounce
        await asyncio.sleep(PROGRESS_DEBOUNCE_INTERVAL + 0.1)

        # Should have only one broadcast with final state
        assert mock_broadcast.call_count == 1
        event = mock_broadcast.call_args[0][0]
        assert event["payload"]["progress"] == 1.0
        assert event["payload"]["current_step"] == "Step 10"

    @pytest.mark.asyncio
    async def test_emit_job_progress_includes_download_fields_in_payload(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test download fields are included in broadcast payload."""
        sample_job.update_progress(50, 100, "Downloading")

        await event_bus_with_broadcast.emit_job_progress(
            sample_job,
            download_speed=8.5,
            eta_seconds=60,
        )

        await asyncio.sleep(PROGRESS_DEBOUNCE_INTERVAL + 0.1)

        event = mock_broadcast.call_args[0][0]
        assert event["payload"]["download_speed"] == 8.5
        assert event["payload"]["eta_seconds"] == 60


class TestJobCompletedEvent:
    """Tests for job completed event emission."""

    @pytest.mark.asyncio
    async def test_emit_job_completed(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test emitting job completed event."""
        sample_job.mark_completed({"downloaded_files": 5})

        await event_bus_with_broadcast.emit_job_completed(sample_job)

        mock_broadcast.assert_called_once()
        event = mock_broadcast.call_args[0][0]

        assert event["event_type"] == "job_completed"
        assert event["payload"]["job_id"] == sample_job.id
        assert event["payload"]["job_type"] == "download_youtube"
        assert event["payload"]["result"] == {"downloaded_files": 5}

    @pytest.mark.asyncio
    async def test_emit_job_completed_with_custom_result(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test emitting completed event with custom result overrides job.result."""
        sample_job.mark_completed({"original": "result"})
        custom_result = {"custom": "result"}

        await event_bus_with_broadcast.emit_job_completed(sample_job, result=custom_result)

        event = mock_broadcast.call_args[0][0]
        assert event["payload"]["result"] == custom_result

    @pytest.mark.asyncio
    async def test_emit_job_completed_flushes_pending_progress(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test completed event flushes pending progress first."""
        sample_job.update_progress(50, 100, "Processing")
        await event_bus_with_broadcast.emit_job_progress(sample_job)

        # Progress is pending
        assert sample_job.id in event_bus_with_broadcast._pending_progress

        sample_job.mark_completed({})
        await event_bus_with_broadcast.emit_job_completed(sample_job)

        # Progress should be flushed (removed from pending)
        assert sample_job.id not in event_bus_with_broadcast._pending_progress

        # Should have 2 broadcasts: progress then completed
        assert mock_broadcast.call_count == 2
        events = [call[0][0] for call in mock_broadcast.call_args_list]
        assert events[0]["event_type"] == "job_progress"
        assert events[1]["event_type"] == "job_completed"


class TestJobFailedEvent:
    """Tests for job failed event emission."""

    @pytest.mark.asyncio
    async def test_emit_job_failed(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test emitting job failed event."""
        sample_job.mark_failed("Download failed: 404 Not Found")

        await event_bus_with_broadcast.emit_job_failed(sample_job)

        mock_broadcast.assert_called_once()
        event = mock_broadcast.call_args[0][0]

        assert event["event_type"] == "job_failed"
        assert event["payload"]["job_id"] == sample_job.id
        assert event["payload"]["error"] == "Download failed: 404 Not Found"

    @pytest.mark.asyncio
    async def test_emit_job_failed_with_custom_error(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test emitting failed event with custom error."""
        sample_job.mark_failed("Original error")

        await event_bus_with_broadcast.emit_job_failed(
            sample_job,
            error="Custom error message",
            error_type="NetworkError",
        )

        event = mock_broadcast.call_args[0][0]
        assert event["payload"]["error"] == "Custom error message"
        assert event["payload"]["error_type"] == "NetworkError"

    @pytest.mark.asyncio
    async def test_emit_job_failed_flushes_pending_progress(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test failed event flushes pending progress first."""
        sample_job.update_progress(30, 100, "Processing")
        await event_bus_with_broadcast.emit_job_progress(sample_job)

        sample_job.mark_failed("Error")
        await event_bus_with_broadcast.emit_job_failed(sample_job)

        # Should have 2 broadcasts: progress then failed
        assert mock_broadcast.call_count == 2
        events = [call[0][0] for call in mock_broadcast.call_args_list]
        assert events[0]["event_type"] == "job_progress"
        assert events[1]["event_type"] == "job_failed"


class TestJobCancelledEvent:
    """Tests for job cancelled event emission."""

    @pytest.mark.asyncio
    async def test_emit_job_cancelled(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test emitting job cancelled event."""
        sample_job.mark_cancelled()

        await event_bus_with_broadcast.emit_job_cancelled(sample_job)

        mock_broadcast.assert_called_once()
        event = mock_broadcast.call_args[0][0]

        assert event["event_type"] == "job_cancelled"
        assert event["payload"]["job_id"] == sample_job.id
        assert event["payload"]["job_type"] == "download_youtube"

    @pytest.mark.asyncio
    async def test_emit_job_cancelled_flushes_pending_progress(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test cancelled event flushes pending progress first."""
        sample_job.update_progress(40, 100, "Processing")
        await event_bus_with_broadcast.emit_job_progress(sample_job)

        sample_job.mark_cancelled()
        await event_bus_with_broadcast.emit_job_cancelled(sample_job)

        # Should have 2 broadcasts: progress then cancelled
        assert mock_broadcast.call_count == 2
        events = [call[0][0] for call in mock_broadcast.call_args_list]
        assert events[0]["event_type"] == "job_progress"
        assert events[1]["event_type"] == "job_cancelled"


class TestJobTimeoutEvent:
    """Tests for job timeout event emission."""

    @pytest.mark.asyncio
    async def test_emit_job_timeout(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test emitting job timeout event."""
        sample_job.timeout_seconds = 300

        await event_bus_with_broadcast.emit_job_timeout(sample_job)

        mock_broadcast.assert_called_once()
        event = mock_broadcast.call_args[0][0]

        assert event["event_type"] == "job_timeout"
        assert event["payload"]["job_id"] == sample_job.id
        assert event["payload"]["job_type"] == "download_youtube"
        assert event["payload"]["timeout_seconds"] == 300

    @pytest.mark.asyncio
    async def test_emit_job_timeout_flushes_pending_progress(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test timeout event flushes pending progress first."""
        sample_job.update_progress(60, 100, "Processing")
        await event_bus_with_broadcast.emit_job_progress(sample_job)

        await event_bus_with_broadcast.emit_job_timeout(sample_job)

        # Should have 2 broadcasts: progress then timeout
        assert mock_broadcast.call_count == 2
        events = [call[0][0] for call in mock_broadcast.call_args_list]
        assert events[0]["event_type"] == "job_progress"
        assert events[1]["event_type"] == "job_timeout"


class TestCancelAndFlushProgress:
    """Tests for cancelling and flushing pending progress."""

    @pytest.mark.asyncio
    async def test_cancel_and_flush_with_no_pending(
        self, event_bus_with_broadcast: EventBus, mock_broadcast: AsyncMock
    ):
        """Test cancel and flush with no pending progress does nothing."""
        await event_bus_with_broadcast._cancel_and_flush_progress("nonexistent-job")

        mock_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_and_flush_cancels_flush_task(
        self,
        event_bus_with_broadcast: EventBus,
        mock_broadcast: AsyncMock,
        sample_job: Job,
    ):
        """Test cancel and flush cancels the pending flush task."""
        sample_job.update_progress(50, 100, "Processing")
        await event_bus_with_broadcast.emit_job_progress(sample_job)

        flush_task = event_bus_with_broadcast._pending_progress[sample_job.id].flush_task

        await event_bus_with_broadcast._cancel_and_flush_progress(sample_job.id)

        # Task should be cancelled
        assert flush_task.cancelled() or flush_task.done()

        # Progress should still be broadcast
        assert mock_broadcast.call_count == 1


class TestShutdown:
    """Tests for event bus shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_tasks(
        self, event_bus_with_broadcast: EventBus, sample_job: Job
    ):
        """Test shutdown cancels all pending flush tasks."""
        sample_job.update_progress(50, 100, "Processing")
        await event_bus_with_broadcast.emit_job_progress(sample_job)

        job2 = Job(type=JobType.IMPORT_NFO)
        job2.mark_running()
        job2.update_progress(30, 100, "Importing")
        await event_bus_with_broadcast.emit_job_progress(job2)

        # Both have pending tasks
        assert len(event_bus_with_broadcast._pending_progress) == 2

        await event_bus_with_broadcast.shutdown()

        # All cleared
        assert len(event_bus_with_broadcast._pending_progress) == 0
        assert event_bus_with_broadcast._started is False

    @pytest.mark.asyncio
    async def test_shutdown_handles_already_completed_tasks(
        self, event_bus_with_broadcast: EventBus, mock_broadcast: AsyncMock, sample_job: Job
    ):
        """Test shutdown handles tasks that already completed."""
        sample_job.update_progress(50, 100, "Processing")
        await event_bus_with_broadcast.emit_job_progress(sample_job)

        # Wait for flush to complete
        await asyncio.sleep(PROGRESS_DEBOUNCE_INTERVAL + 0.1)

        # Shutdown should not raise
        await event_bus_with_broadcast.shutdown()


class TestGlobalEventBus:
    """Tests for global event bus functions."""

    def test_get_event_bus_raises_before_init(self):
        """Test get_event_bus raises if not initialized."""
        with pytest.raises(RuntimeError, match="Event bus not initialized"):
            get_event_bus()

    def test_init_event_bus_creates_instance(self):
        """Test init_event_bus creates global instance."""
        bus = init_event_bus()

        assert bus is not None
        assert isinstance(bus, EventBus)
        assert get_event_bus() is bus

    def test_init_event_bus_returns_new_instance(self):
        """Test init_event_bus creates new instance each time."""
        bus1 = init_event_bus()
        bus2 = init_event_bus()

        assert bus1 is not bus2
        assert get_event_bus() is bus2

    def test_reset_event_bus_clears_global(self):
        """Test reset_event_bus clears the global instance."""
        init_event_bus()
        reset_event_bus()

        with pytest.raises(RuntimeError):
            get_event_bus()


class TestMultipleJobs:
    """Tests for handling multiple concurrent jobs."""

    @pytest.mark.asyncio
    async def test_multiple_jobs_independent_debounce(
        self, event_bus_with_broadcast: EventBus, mock_broadcast: AsyncMock
    ):
        """Test each job has independent debounce tracking."""
        job1 = Job(type=JobType.DOWNLOAD_YOUTUBE)
        job1.mark_running()
        job1.update_progress(50, 100, "Job 1 progress")

        job2 = Job(type=JobType.IMPORT_NFO)
        job2.mark_running()
        job2.update_progress(30, 100, "Job 2 progress")

        await event_bus_with_broadcast.emit_job_progress(job1)
        await event_bus_with_broadcast.emit_job_progress(job2)

        # Both should have separate pending entries
        assert job1.id in event_bus_with_broadcast._pending_progress
        assert job2.id in event_bus_with_broadcast._pending_progress

        # Wait for both to flush
        await asyncio.sleep(PROGRESS_DEBOUNCE_INTERVAL + 0.1)

        # Both should be broadcast
        assert mock_broadcast.call_count == 2

    @pytest.mark.asyncio
    async def test_terminal_event_only_flushes_own_progress(
        self, event_bus_with_broadcast: EventBus, mock_broadcast: AsyncMock
    ):
        """Test terminal event only flushes progress for that job."""
        job1 = Job(type=JobType.DOWNLOAD_YOUTUBE)
        job1.mark_running()
        job1.update_progress(50, 100, "Job 1")

        job2 = Job(type=JobType.IMPORT_NFO)
        job2.mark_running()
        job2.update_progress(30, 100, "Job 2")

        await event_bus_with_broadcast.emit_job_progress(job1)
        await event_bus_with_broadcast.emit_job_progress(job2)

        # Complete job1
        job1.mark_completed({})
        await event_bus_with_broadcast.emit_job_completed(job1)

        # Job1 progress flushed, job2 still pending
        assert job1.id not in event_bus_with_broadcast._pending_progress
        assert job2.id in event_bus_with_broadcast._pending_progress

        # Should have 2 calls: job1 progress + job1 completed
        assert mock_broadcast.call_count == 2
