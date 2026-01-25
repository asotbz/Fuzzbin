"""Unit tests for VideoService."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fuzzbin.services.video_service import (
    DeleteResult,
    DuplicatesResult,
    OrganizeResult,
    RestoreResult,
    VideoService,
    VideoWithRelationships,
)
from fuzzbin.services.base import (
    NotFoundError,
    ValidationError,
)


@pytest.fixture
def mock_repository():
    """Mock VideoRepository for testing."""
    repository = AsyncMock()

    # Video CRUD
    repository.get_video_by_id = AsyncMock(
        return_value={
            "id": 1,
            "title": "Test Video",
            "artist": "Test Artist",
            "album": "Test Album",
            "year": 2023,
            "video_file_path": "/media/test.mp4",
            "nfo_file_path": "/media/test.nfo",
            "status": "discovered",
        }
    )
    repository.create_video = AsyncMock(return_value=1)
    repository.update_video = AsyncMock()
    repository.delete_video = AsyncMock()
    repository.restore_video = AsyncMock()
    repository.hard_delete_video = AsyncMock()
    repository.update_status = AsyncMock()

    # Relationships
    repository.get_video_artists = AsyncMock(return_value=[{"id": 1, "name": "Test Artist"}])
    repository.get_video_collections = AsyncMock(return_value=[])
    repository.get_video_tags = AsyncMock(return_value=[{"id": 1, "name": "rock"}])

    # Artist operations
    repository.upsert_artist = AsyncMock(return_value=1)
    repository.link_video_artist = AsyncMock()

    # Transaction
    repository.transaction = MagicMock()
    repository.transaction.__aenter__ = AsyncMock()
    repository.transaction.__aexit__ = AsyncMock()

    # Query builder
    query = AsyncMock()
    query.where_title = MagicMock(return_value=query)
    query.where_artist = MagicMock(return_value=query)
    query.where_status = MagicMock(return_value=query)
    query.where_imvdb_id = MagicMock(return_value=query)
    query.where_youtube_id = MagicMock(return_value=query)
    query.execute = AsyncMock(return_value=[])
    query.count = AsyncMock(return_value=10)
    repository.query = MagicMock(return_value=query)

    return repository


@pytest.fixture
def mock_file_manager():
    """Mock FileManager for testing."""
    file_manager = AsyncMock()
    file_manager.organize_video = AsyncMock()
    file_manager.hard_delete = AsyncMock()
    file_manager.soft_delete = AsyncMock(return_value=Path("/trash/test.mp4"))
    file_manager.restore = AsyncMock(return_value=Path("/media/test.mp4"))
    file_manager.find_duplicates_by_hash = AsyncMock(return_value=[])
    file_manager.find_duplicates_by_metadata = AsyncMock(return_value=[])
    file_manager.find_all_duplicates = AsyncMock(return_value=[])
    file_manager.generate_thumbnail = AsyncMock(return_value=Path("/cache/thumb_1.jpg"))
    file_manager.verify_library = AsyncMock()
    return file_manager


@pytest.fixture
def video_service(mock_repository, mock_file_manager):
    """Create VideoService instance for testing."""
    service = VideoService(
        repository=mock_repository,
        file_manager=mock_file_manager,
    )
    return service


# ==================== CRUD Tests ====================


class TestVideoServiceCRUD:
    """Tests for VideoService CRUD operations."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, video_service, mock_repository):
        """Test successful video retrieval."""
        video = await video_service.get_by_id(1)

        assert video["id"] == 1
        assert video["title"] == "Test Video"
        mock_repository.get_video_by_id.assert_called_once_with(1, include_deleted=False)

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, video_service, mock_repository):
        """Test NotFoundError when video doesn't exist."""
        mock_repository.get_video_by_id.side_effect = Exception("Not found")

        with pytest.raises(NotFoundError) as exc_info:
            await video_service.get_by_id(999)

        assert exc_info.value.resource_type == "video"
        assert exc_info.value.resource_id == 999

    @pytest.mark.asyncio
    async def test_get_with_relationships(self, video_service, mock_repository):
        """Test getting video with relationships loaded."""
        result = await video_service.get_with_relationships(1)

        assert isinstance(result, VideoWithRelationships)
        assert result.id == 1
        assert result.title == "Test Video"
        assert len(result.artists) == 1
        assert len(result.tags) == 1
        mock_repository.get_video_artists.assert_called_once_with(1)
        mock_repository.get_video_collections.assert_called_once_with(1)
        mock_repository.get_video_tags.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_create_video_success(self, video_service, mock_repository):
        """Test successful video creation."""
        result = await video_service.create(
            title="New Video",
            artist="New Artist",
            year=2024,
        )

        assert isinstance(result, VideoWithRelationships)
        mock_repository.create_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_video_requires_title(self, video_service):
        """Test that title is required."""
        with pytest.raises(ValidationError) as exc_info:
            await video_service.create(title="")

        assert exc_info.value.field == "title"

    @pytest.mark.asyncio
    async def test_create_with_artists(self, video_service, mock_repository):
        """Test creating video with artists."""
        artists = [
            {"name": "Main Artist", "role": "artist"},
            {"name": "Featured Artist", "role": "featured"},
        ]

        result = await video_service.create_with_artists(
            title="New Video",
            artists=artists,
        )

        assert isinstance(result, VideoWithRelationships)
        assert mock_repository.upsert_artist.call_count == 2
        assert mock_repository.link_video_artist.call_count == 2

    @pytest.mark.asyncio
    async def test_update_video(self, video_service, mock_repository):
        """Test video update."""
        result = await video_service.update(1, title="Updated Title")

        assert isinstance(result, VideoWithRelationships)
        mock_repository.update_video.assert_called_once_with(1, title="Updated Title")

    @pytest.mark.asyncio
    async def test_update_status(self, video_service, mock_repository):
        """Test status update with tracking."""
        result = await video_service.update_status(
            video_id=1,
            new_status="downloaded",
            reason="Download complete",
        )

        assert isinstance(result, VideoWithRelationships)
        mock_repository.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_soft_delete(self, video_service, mock_repository):
        """Test soft delete."""
        await video_service.delete(1)
        mock_repository.delete_video.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_restore(self, video_service, mock_repository):
        """Test restore soft-deleted video."""
        result = await video_service.restore(1)

        assert isinstance(result, VideoWithRelationships)
        mock_repository.restore_video.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_hard_delete_record(self, video_service, mock_repository):
        """Test permanent deletion of record."""
        await video_service.hard_delete(1)
        mock_repository.hard_delete_video.assert_called_once_with(1)


# ==================== Existence Check Tests ====================


class TestVideoServiceExistence:
    """Tests for video existence checks."""

    @pytest.mark.asyncio
    async def test_exists_returns_false_when_not_found(self, video_service, mock_repository):
        """Test exists returns False when no match."""
        mock_repository.query().execute = AsyncMock(return_value=[])

        result = await video_service.exists("Unknown", "Unknown Artist")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_returns_true_when_found(self, video_service, mock_repository):
        """Test exists returns True when match found."""
        mock_repository.query().execute = AsyncMock(return_value=[{"id": 1}])

        result = await video_service.exists("Known Title", "Known Artist")
        assert result is True

    @pytest.mark.asyncio
    async def test_find_by_external_id_imvdb(self, video_service, mock_repository):
        """Test finding by IMVDb ID."""
        mock_repository.query().execute = AsyncMock(
            return_value=[{"id": 1, "imvdb_video_id": "abc"}]
        )

        result = await video_service.find_by_external_id(imvdb_video_id="abc")
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_find_by_external_id_youtube(self, video_service, mock_repository):
        """Test finding by YouTube ID."""
        mock_repository.query().execute = AsyncMock(return_value=[{"id": 1, "youtube_id": "xyz"}])

        result = await video_service.find_by_external_id(youtube_id="xyz")
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_find_by_external_id_none(self, video_service):
        """Test returns None when no ID provided."""
        result = await video_service.find_by_external_id()
        assert result is None


# ==================== File Operations Tests ====================


class TestVideoServiceFileOps:
    """Tests for VideoService file operations."""

    @pytest.mark.asyncio
    async def test_organize_success(self, video_service, mock_file_manager):
        """Test successful organize operation."""
        # Mock organize_video return
        mock_paths = MagicMock()
        mock_paths.video_path = Path("/organized/test.mp4")
        mock_paths.nfo_path = Path("/organized/test.nfo")
        mock_file_manager.organize_video.return_value = mock_paths

        result = await video_service.organize(1, dry_run=False)

        assert isinstance(result, OrganizeResult)
        assert result.video_id == 1
        assert result.target_video_path == "/organized/test.mp4"

    @pytest.mark.asyncio
    async def test_organize_dry_run(self, video_service, mock_file_manager):
        """Test organize with dry_run=True."""
        mock_paths = MagicMock()
        mock_paths.video_path = Path("/organized/test.mp4")
        mock_paths.nfo_path = Path("/organized/test.nfo")
        mock_file_manager.organize_video.return_value = mock_paths

        result = await video_service.organize(1, dry_run=True)

        assert result.dry_run is True
        mock_file_manager.organize_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_files_soft(self, video_service, mock_file_manager):
        """Test soft delete of files."""
        result = await video_service.delete_files(1, hard_delete=False)

        assert isinstance(result, DeleteResult)
        assert result.hard_delete is False
        assert result.trash_path == "/trash/test.mp4"
        mock_file_manager.soft_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_files_hard(self, video_service, mock_file_manager):
        """Test hard delete of files."""
        result = await video_service.delete_files(1, hard_delete=True)

        assert isinstance(result, DeleteResult)
        assert result.hard_delete is True
        assert result.trash_path is None
        mock_file_manager.hard_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_files_no_path_raises(self, video_service, mock_repository):
        """Test error when video has no file path."""
        mock_repository.get_video_by_id.return_value = {
            "id": 1,
            "title": "Test",
            "video_file_path": None,
        }

        with pytest.raises(ValidationError) as exc_info:
            await video_service.delete_files(1)

        assert exc_info.value.field == "video_file_path"

    @pytest.mark.asyncio
    async def test_restore_files(self, video_service, mock_repository, mock_file_manager):
        """Test restoring files from trash."""
        # Mock a deleted video for restore
        mock_repository.get_video_by_id.return_value = {
            "id": 1,
            "title": "Test Video",
            "artist": "Test Artist",
            "video_file_path": "/trash/test.mp4",
            "nfo_file_path": "/trash/test.nfo",
            "is_deleted": True,
            "status": "deleted",
        }

        result = await video_service.restore_files(1)

        assert isinstance(result, RestoreResult)
        assert result.restored is True
        assert result.restored_path == "/media/test.mp4"


# ==================== Duplicate Detection Tests ====================


class TestVideoServiceDuplicates:
    """Tests for duplicate detection and resolution."""

    @pytest.mark.asyncio
    async def test_find_duplicates(self, video_service, mock_file_manager):
        """Test finding duplicates."""
        mock_file_manager.find_duplicates.return_value = []

        result = await video_service.find_duplicates(1)

        assert isinstance(result, DuplicatesResult)
        assert result.video_id == 1
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_resolve_duplicates(self, video_service, mock_repository, mock_file_manager):
        """Test resolving duplicates."""
        # Setup mock for remove_ids
        mock_repository.get_video_by_id.return_value = {
            "id": 2,
            "video_file_path": "/media/dup.mp4",
        }

        result = await video_service.resolve_duplicates(
            keep_video_id=1,
            remove_video_ids=[2, 3],
            hard_delete=False,
        )

        assert result.kept_video_id == 1
        assert len(result.removed_video_ids) > 0


# ==================== Thumbnail Tests ====================


class TestVideoServiceThumbnails:
    """Tests for thumbnail generation."""

    @pytest.mark.asyncio
    async def test_get_thumbnail(self, video_service, mock_repository, mock_file_manager):
        """Test thumbnail retrieval."""
        # Mock a video with existing file
        mock_repository.get_video_by_id.return_value = {
            "id": 1,
            "title": "Test Video",
            "video_file_path": "/media/test.mp4",
        }

        # Mock Path.exists() to return True
        with patch("fuzzbin.services.video_service.Path") as mock_path:
            mock_path.return_value.exists.return_value = True

            result = await video_service.get_thumbnail(1)

            assert result == Path("/cache/thumb_1.jpg")
            mock_file_manager.generate_thumbnail.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_thumbnail_no_file_raises(self, video_service, mock_repository):
        """Test error when video has no file path."""
        mock_repository.get_video_by_id.return_value = {
            "id": 1,
            "video_file_path": None,
        }

        with pytest.raises(NotFoundError):
            await video_service.get_thumbnail(1)


# ==================== Stats Tests ====================


class TestVideoServiceStats:
    """Tests for cached statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, video_service, mock_repository):
        """Test getting library stats."""
        result = await video_service.get_stats()

        assert "total_videos" in result
        assert "by_status" in result
