"""Unit tests for TagService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fuzzbin.services.tag_service import TagService


@pytest.fixture
def mock_repository():
    """Mock VideoRepository for TagService tests."""
    repository = AsyncMock()

    repository.get_video_by_id = AsyncMock(
        return_value={
            "id": 1,
            "title": "Test Video",
            "artist": "Test Artist",
            "year": 1995,
            "video_file_path": "/media/test.mp4",
            "nfo_file_path": "/media/test.nfo",
        }
    )

    repository.set_video_tags = AsyncMock()
    repository.add_video_tag = AsyncMock()
    repository.remove_video_tag = AsyncMock()
    repository.get_video_tags = AsyncMock(
        return_value=[
            {"id": 1, "name": "rock", "normalized_name": "rock", "usage_count": 5},
            {"id": 2, "name": "90s", "normalized_name": "90s", "usage_count": 3},
        ]
    )
    repository.bulk_apply_tags = AsyncMock(
        return_value={
            "success_ids": [1, 2, 3],
            "failed_ids": [],
            "errors": {},
        }
    )

    return repository


@pytest.fixture
def tag_service(mock_repository):
    """Create TagService instance for testing."""
    return TagService(repository=mock_repository)


@pytest.fixture
def mock_config_nfo_enabled():
    """Mock config with NFO write enabled."""
    config = MagicMock()
    config.nfo.write_musicvideo_nfo = True
    return config


@pytest.fixture
def mock_config_nfo_disabled():
    """Mock config with NFO write disabled."""
    config = MagicMock()
    config.nfo.write_musicvideo_nfo = False
    return config


class TestSetVideoTags:
    """Tests for TagService.set_video_tags()."""

    async def test_set_tags_calls_repo(self, tag_service, mock_repository):
        """Test that set_video_tags delegates to repository."""
        with patch.object(tag_service, "_export_nfo_for_video", new_callable=AsyncMock):
            with patch.object(tag_service, "_emit_tags_changed", new_callable=AsyncMock):
                result = await tag_service.set_video_tags(1, ["rock", "grunge"], source="manual")

        mock_repository.set_video_tags.assert_called_once_with(
            1, ["rock", "grunge"], source="manual", replace_existing=True
        )
        assert len(result) == 2

    async def test_set_tags_replace_false(self, tag_service, mock_repository):
        """Test additive tag setting."""
        with patch.object(tag_service, "_export_nfo_for_video", new_callable=AsyncMock):
            with patch.object(tag_service, "_emit_tags_changed", new_callable=AsyncMock):
                await tag_service.set_video_tags(
                    1, ["pop"], source="manual", replace_existing=False
                )

        mock_repository.set_video_tags.assert_called_once_with(
            1, ["pop"], source="manual", replace_existing=False
        )

    async def test_set_tags_triggers_nfo_export(self, tag_service, mock_config_nfo_enabled):
        """Test that NFO export is triggered when enabled."""
        mock_exporter = AsyncMock()
        mock_exporter.export_video_to_nfo = AsyncMock()

        with (
            patch.object(tag_service, "_get_config", return_value=mock_config_nfo_enabled),
            patch("fuzzbin.core.db.exporter.NFOExporter", return_value=mock_exporter),
            patch.object(tag_service, "_emit_tags_changed", new_callable=AsyncMock),
        ):
            await tag_service.set_video_tags(1, ["rock"])

        mock_exporter.export_video_to_nfo.assert_called_once_with(1)

    async def test_set_tags_skips_nfo_when_disabled(self, tag_service, mock_config_nfo_disabled):
        """Test that NFO export is skipped when disabled."""
        with (
            patch.object(tag_service, "_get_config", return_value=mock_config_nfo_disabled),
            patch("fuzzbin.core.db.exporter.NFOExporter") as mock_cls,
            patch.object(tag_service, "_emit_tags_changed", new_callable=AsyncMock),
        ):
            await tag_service.set_video_tags(1, ["rock"])

        mock_cls.assert_not_called()

    async def test_set_tags_emits_event(self, tag_service):
        """Test that a video_updated event is emitted."""
        mock_event_bus = AsyncMock()

        with (
            patch.object(tag_service, "_export_nfo_for_video", new_callable=AsyncMock),
            patch("fuzzbin.core.event_bus.get_event_bus", return_value=mock_event_bus),
        ):
            await tag_service.set_video_tags(1, ["rock"])

        mock_event_bus.emit_video_updated.assert_called_once_with(
            video_id=1, fields_changed=["tags"]
        )


class TestAddVideoTag:
    """Tests for TagService.add_video_tag()."""

    async def test_add_tag_calls_repo(self, tag_service, mock_repository):
        """Test that add_video_tag delegates to repository."""
        with patch.object(tag_service, "_export_nfo_for_video", new_callable=AsyncMock):
            with patch.object(tag_service, "_emit_tags_changed", new_callable=AsyncMock):
                await tag_service.add_video_tag(1, 5)

        mock_repository.add_video_tag.assert_called_once_with(1, 5)

    async def test_add_tag_triggers_nfo_export(self, tag_service, mock_config_nfo_enabled):
        """Test that NFO export is triggered."""
        mock_exporter = AsyncMock()

        with (
            patch.object(tag_service, "_get_config", return_value=mock_config_nfo_enabled),
            patch("fuzzbin.core.db.exporter.NFOExporter", return_value=mock_exporter),
            patch.object(tag_service, "_emit_tags_changed", new_callable=AsyncMock),
        ):
            await tag_service.add_video_tag(1, 5)

        mock_exporter.export_video_to_nfo.assert_called_once_with(1)


class TestRemoveVideoTag:
    """Tests for TagService.remove_video_tag()."""

    async def test_remove_tag_calls_repo(self, tag_service, mock_repository):
        """Test that remove_video_tag delegates to repository."""
        with patch.object(tag_service, "_export_nfo_for_video", new_callable=AsyncMock):
            with patch.object(tag_service, "_emit_tags_changed", new_callable=AsyncMock):
                await tag_service.remove_video_tag(1, 5)

        mock_repository.remove_video_tag.assert_called_once_with(1, 5)

    async def test_remove_tag_triggers_nfo_export(self, tag_service, mock_config_nfo_enabled):
        """Test that NFO export is triggered."""
        mock_exporter = AsyncMock()

        with (
            patch.object(tag_service, "_get_config", return_value=mock_config_nfo_enabled),
            patch("fuzzbin.core.db.exporter.NFOExporter", return_value=mock_exporter),
            patch.object(tag_service, "_emit_tags_changed", new_callable=AsyncMock),
        ):
            await tag_service.remove_video_tag(1, 5)

        mock_exporter.export_video_to_nfo.assert_called_once_with(1)


class TestBulkApplyTags:
    """Tests for TagService.bulk_apply_tags()."""

    async def test_bulk_apply_calls_repo(self, tag_service, mock_repository):
        """Test that bulk_apply_tags delegates to repository."""
        with patch.object(tag_service, "_submit_selective_nfo_export", new_callable=AsyncMock):
            result = await tag_service.bulk_apply_tags([1, 2, 3], ["rock", "90s"])

        mock_repository.bulk_apply_tags.assert_called_once_with(
            video_ids=[1, 2, 3], tag_names=["rock", "90s"], replace=False
        )
        assert result["success_ids"] == [1, 2, 3]

    async def test_bulk_apply_replace_mode(self, tag_service, mock_repository):
        """Test bulk apply with replace=True."""
        with patch.object(tag_service, "_submit_selective_nfo_export", new_callable=AsyncMock):
            await tag_service.bulk_apply_tags([1, 2], ["pop"], replace=True)

        mock_repository.bulk_apply_tags.assert_called_once_with(
            video_ids=[1, 2], tag_names=["pop"], replace=True
        )

    async def test_bulk_apply_submits_nfo_job(self, tag_service, mock_config_nfo_enabled):
        """Test that a selective NFO export job is submitted for successful IDs."""
        mock_queue = AsyncMock()

        with (
            patch.object(tag_service, "_get_config", return_value=mock_config_nfo_enabled),
            patch("fuzzbin.tasks.queue.get_job_queue", return_value=mock_queue),
        ):
            await tag_service.bulk_apply_tags([1, 2, 3], ["rock"])

        mock_queue.submit.assert_called_once()
        submitted_job = mock_queue.submit.call_args[0][0]
        assert submitted_job.type.value == "export_nfo_selective"
        assert submitted_job.metadata["video_ids"] == [1, 2, 3]

    async def test_bulk_apply_skips_nfo_when_disabled(self, tag_service, mock_config_nfo_disabled):
        """Test that NFO job is not submitted when NFO export is disabled."""
        with (
            patch.object(tag_service, "_get_config", return_value=mock_config_nfo_disabled),
            patch("fuzzbin.tasks.queue.get_job_queue") as mock_get_queue,
        ):
            await tag_service.bulk_apply_tags([1, 2], ["rock"])

        mock_get_queue.assert_not_called()

    async def test_bulk_apply_no_nfo_job_when_all_failed(self, tag_service, mock_repository):
        """Test that no NFO job is submitted when all videos failed."""
        mock_repository.bulk_apply_tags.return_value = {
            "success_ids": [],
            "failed_ids": [1, 2, 3],
            "errors": {"1": "err", "2": "err", "3": "err"},
        }

        with patch.object(
            tag_service, "_submit_selective_nfo_export", new_callable=AsyncMock
        ) as mock_submit:
            await tag_service.bulk_apply_tags([1, 2, 3], ["rock"])

        # Not called because success_ids is empty
        mock_submit.assert_not_called()


class TestNFOExportResilience:
    """Tests for NFO export error handling."""

    async def test_nfo_export_failure_does_not_break_tag_op(
        self, tag_service, mock_config_nfo_enabled
    ):
        """Test that NFO export failure doesn't affect the tag operation."""
        mock_exporter = AsyncMock()
        mock_exporter.export_video_to_nfo = AsyncMock(side_effect=Exception("Disk full"))

        with (
            patch.object(tag_service, "_get_config", return_value=mock_config_nfo_enabled),
            patch("fuzzbin.core.db.exporter.NFOExporter", return_value=mock_exporter),
            patch.object(tag_service, "_emit_tags_changed", new_callable=AsyncMock),
        ):
            # Should not raise despite export failure
            result = await tag_service.set_video_tags(1, ["rock"])

        # Tags should still be returned (from get_video_tags mock)
        assert len(result) == 2

    async def test_event_bus_failure_does_not_break_tag_op(self, tag_service):
        """Test that event bus failure doesn't affect the tag operation."""
        with (
            patch.object(tag_service, "_export_nfo_for_video", new_callable=AsyncMock),
            patch(
                "fuzzbin.core.event_bus.get_event_bus",
                side_effect=RuntimeError("Not initialized"),
            ),
        ):
            # Should not raise
            result = await tag_service.set_video_tags(1, ["rock"])

        assert len(result) == 2
