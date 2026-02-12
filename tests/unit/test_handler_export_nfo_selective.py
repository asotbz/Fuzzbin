"""Unit tests for handle_export_nfo_selective handler."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from fuzzbin.tasks.models import Job, JobStatus, JobType


@pytest.fixture
def selective_export_job():
    """Create a job for selective NFO export."""
    return Job(
        type=JobType.EXPORT_NFO_SELECTIVE,
        metadata={"video_ids": [1, 2, 3]},
    )


class TestHandleExportNFOSelective:
    """Tests for handle_export_nfo_selective handler."""

    async def test_exports_nfos_for_given_video_ids(self, selective_export_job):
        """Test that NFOs are exported for each video ID."""
        mock_repo = AsyncMock()
        mock_repo.get_video_by_id = AsyncMock(
            side_effect=lambda vid: {
                "id": vid,
                "nfo_file_path": f"/media/video_{vid}.nfo",
                "video_file_path": f"/media/video_{vid}.mp4",
            }
        )

        mock_exporter = AsyncMock()
        mock_exporter.export_video_to_nfo = AsyncMock(return_value=(Path("/media/video.nfo"), True))

        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.core.db.exporter.NFOExporter", return_value=mock_exporter),
        ):
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repo)

            from fuzzbin.tasks.handlers import handle_export_nfo_selective

            await handle_export_nfo_selective(selective_export_job)

        assert mock_exporter.export_video_to_nfo.call_count == 3
        assert selective_export_job.status == JobStatus.COMPLETED
        assert selective_export_job.result["exported"] == 3
        assert selective_export_job.result["failed"] == 0

    async def test_empty_video_ids_completes_immediately(self):
        """Test that empty video_ids list completes without doing work."""
        job = Job(
            type=JobType.EXPORT_NFO_SELECTIVE,
            metadata={"video_ids": []},
        )

        from fuzzbin.tasks.handlers import handle_export_nfo_selective

        await handle_export_nfo_selective(job)

        assert job.status == JobStatus.COMPLETED
        assert job.result == {"exported": 0, "skipped": 0, "failed": 0}

    async def test_handles_export_failures_gracefully(self, selective_export_job):
        """Test that individual export failures don't stop the job."""
        mock_repo = AsyncMock()
        mock_repo.get_video_by_id = AsyncMock(
            side_effect=lambda vid: {
                "id": vid,
                "nfo_file_path": f"/media/video_{vid}.nfo",
            }
        )

        mock_exporter = AsyncMock()
        # First succeeds, second fails, third succeeds
        mock_exporter.export_video_to_nfo = AsyncMock(
            side_effect=[
                (Path("/media/video_1.nfo"), True),
                Exception("Write failed"),
                (Path("/media/video_3.nfo"), True),
            ]
        )

        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.core.db.exporter.NFOExporter", return_value=mock_exporter),
        ):
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repo)

            from fuzzbin.tasks.handlers import handle_export_nfo_selective

            await handle_export_nfo_selective(selective_export_job)

        assert selective_export_job.result["exported"] == 2
        assert selective_export_job.result["failed"] == 1

    async def test_skips_videos_without_paths(self):
        """Test that videos with no file paths are skipped."""
        job = Job(
            type=JobType.EXPORT_NFO_SELECTIVE,
            metadata={"video_ids": [1]},
        )

        mock_repo = AsyncMock()
        mock_repo.get_video_by_id = AsyncMock(
            return_value={
                "id": 1,
                "nfo_file_path": None,
                "video_file_path": None,
            }
        )

        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.core.db.exporter.NFOExporter"),
        ):
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repo)

            from fuzzbin.tasks.handlers import handle_export_nfo_selective

            await handle_export_nfo_selective(job)

        assert job.result["skipped"] == 1
        assert job.result["exported"] == 0

    async def test_derives_nfo_path_from_video_path(self):
        """Test fallback to deriving NFO path from video file path."""
        job = Job(
            type=JobType.EXPORT_NFO_SELECTIVE,
            metadata={"video_ids": [1]},
        )

        mock_repo = AsyncMock()
        mock_repo.get_video_by_id = AsyncMock(
            return_value={
                "id": 1,
                "nfo_file_path": None,
                "video_file_path": "/media/Artist/video.mp4",
            }
        )

        mock_exporter = AsyncMock()
        mock_exporter.export_video_to_nfo = AsyncMock(
            return_value=(Path("/media/Artist/video.nfo"), True)
        )

        with (
            patch("fuzzbin.tasks.handlers.fuzzbin") as mock_fuzzbin,
            patch("fuzzbin.core.db.exporter.NFOExporter", return_value=mock_exporter),
        ):
            mock_fuzzbin.get_repository = AsyncMock(return_value=mock_repo)

            from fuzzbin.tasks.handlers import handle_export_nfo_selective

            await handle_export_nfo_selective(job)

        # Verify the derived NFO path was used
        call_args = mock_exporter.export_video_to_nfo.call_args
        assert call_args[1]["nfo_path"] == Path("/media/Artist/video.nfo")
