"""Unit tests for file manager."""

import pytest
import pytest_asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fuzzbin.common.config import TrashConfig, OrganizerConfig
from fuzzbin.core.file_manager import (
    FileManager,
    FileManagerError,
    FileNotFoundError as FMFileNotFoundError,
    FileExistsError as FMFileExistsError,
    HashMismatchError,
    RollbackError,
    FileTooLargeError,
    DuplicateCandidate,
    LibraryIssue,
    LibraryReport,
)
from fuzzbin.core.organizer import MediaPaths
from fuzzbin.parsers import MusicVideoNFO


class TestTrashConfig:
    """Tests for TrashConfig."""

    def test_default_values(self):
        """Test default configuration values.
        
        Note: TrashConfig contains trash settings including cleanup schedule.
        """
        config = TrashConfig()
        assert config.trash_dir == ".trash"
        assert config.enabled is True
        assert config.retention_days == 30

    def test_custom_trash_dir(self):
        """Test custom trash_dir configuration."""
        config = TrashConfig(trash_dir=".deleted")
        assert config.trash_dir == ".deleted"


class TestFileManagerInit:
    """Tests for FileManager initialization."""

    def test_basic_init(self, tmp_path):
        """Test basic initialization."""
        config = TrashConfig()
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        fm = FileManager(config, library_dir=library_dir, config_dir=config_dir)

        assert fm.config == config
        assert fm.library_dir == library_dir
        assert fm.workspace_root == library_dir  # Backward compat alias
        assert fm.trash_dir == library_dir / ".trash"
        assert fm.thumbnail_cache_dir == config_dir / ".thumbnails"
        assert fm.organizer_config is None

    def test_init_with_organizer_config(self, tmp_path):
        """Test initialization with organizer config."""
        config = TrashConfig()
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        org_config = OrganizerConfig(path_pattern="{artist}/{title}")
        fm = FileManager(config, library_dir=library_dir, config_dir=config_dir, organizer_config=org_config)

        assert fm.organizer_config == org_config

    def test_from_config(self, tmp_path):
        """Test factory method."""
        config = TrashConfig(trash_dir=".deleted")
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        fm = FileManager.from_config(config, library_dir=library_dir, config_dir=config_dir)

        assert fm.config == config
        assert fm.trash_dir == library_dir / ".deleted"


class TestComputeFileHash:
    """Tests for compute_file_hash method."""

    @pytest_asyncio.fixture
    async def file_manager(self, tmp_path):
        """Create file manager instance.
        
        Note: chunk_size is now a class default (DEFAULT_CHUNK_SIZE = 8192).
        """
        config = TrashConfig()
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        return FileManager(config, library_dir=library_dir, config_dir=config_dir)

    @pytest_asyncio.fixture
    async def test_file(self, tmp_path):
        """Create a test file with known content."""
        test_file = tmp_path / "test_video.mp4"
        test_file.write_bytes(b"test video content for hashing")
        return test_file

    @pytest.mark.asyncio
    async def test_hash_sha256(self, file_manager, test_file):
        """Test SHA256 hashing."""
        file_hash = await file_manager.compute_file_hash(test_file)
        
        # Hash should be 64 character hex string
        assert len(file_hash) == 64
        assert all(c in "0123456789abcdef" for c in file_hash)

    @pytest.mark.asyncio
    async def test_hash_consistent(self, file_manager, test_file):
        """Test that same file produces same hash."""
        hash1 = await file_manager.compute_file_hash(test_file)
        hash2 = await file_manager.compute_file_hash(test_file)
        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_hash_file_not_found(self, file_manager, tmp_path):
        """Test error for non-existent file."""
        non_existent = tmp_path / "does_not_exist.mp4"
        
        with pytest.raises(FMFileNotFoundError):
            await file_manager.compute_file_hash(non_existent)

    @pytest.mark.asyncio
    async def test_hash_file_too_large(self, tmp_path):
        """Test error for file exceeding max size.
        
        Note: max_file_size is now a class default (DEFAULT_MAX_FILE_SIZE = None).
        We override it on the instance to test the validation logic.
        """
        config = TrashConfig()
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        fm = FileManager(config, library_dir=library_dir, config_dir=config_dir)
        # Override the class default for testing
        fm.DEFAULT_MAX_FILE_SIZE = 10
        
        # Create file larger than limit
        large_file = tmp_path / "large.mp4"
        large_file.write_bytes(b"x" * 100)
        
        with pytest.raises(FileTooLargeError):
            await fm.compute_file_hash(large_file)


class TestVerifyFileExists:
    """Tests for verify_file_exists method."""

    @pytest_asyncio.fixture
    async def file_manager(self, tmp_path):
        """Create file manager instance."""
        config = TrashConfig()
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        return FileManager(config, library_dir=library_dir, config_dir=config_dir)

    @pytest.mark.asyncio
    async def test_existing_file(self, file_manager, tmp_path):
        """Test returns True for existing file."""
        test_file = tmp_path / "exists.mp4"
        test_file.write_text("content")
        
        assert await file_manager.verify_file_exists(test_file) is True

    @pytest.mark.asyncio
    async def test_non_existing_file(self, file_manager, tmp_path):
        """Test returns False for non-existing file."""
        non_existent = tmp_path / "does_not_exist.mp4"
        
        assert await file_manager.verify_file_exists(non_existent) is False


class TestMoveVideoAtomic:
    """Tests for move_video_atomic method."""

    @pytest_asyncio.fixture
    async def file_manager(self, tmp_path):
        """Create file manager instance.
        
        Note: verify_after_move is now a class default (DEFAULT_VERIFY_AFTER_MOVE = True).
        """
        config = TrashConfig()
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        return FileManager(config, library_dir=library_dir, config_dir=config_dir)

    @pytest_asyncio.fixture
    async def source_file(self, tmp_path):
        """Create a source video file."""
        source_dir = tmp_path / "downloads"
        source_dir.mkdir()
        source_file = source_dir / "video.mp4"
        source_file.write_bytes(b"test video content")
        return source_file

    @pytest_asyncio.fixture
    async def mock_repository(self):
        """Create mock repository."""
        repo = MagicMock()
        repo.update_video = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_move_success(self, file_manager, source_file, mock_repository, tmp_path):
        """Test successful file move."""
        target_dir = tmp_path / "organized"
        target_dir.mkdir()
        
        target_paths = MediaPaths(
            video_path=target_dir / "artist" / "title.mp4",
            nfo_path=target_dir / "artist" / "title.nfo",
        )
        
        result = await file_manager.move_video_atomic(
            video_id=123,
            source_video_path=source_file,
            target_paths=target_paths,
            repository=mock_repository,
        )
        
        # Source should be gone
        assert not source_file.exists()
        
        # Target should exist
        assert target_paths.video_path.exists()
        
        # Result should match target
        assert result == target_paths
        
        # Repository should be updated
        mock_repository.update_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_move_dry_run(self, file_manager, source_file, mock_repository, tmp_path):
        """Test dry run doesn't move files."""
        target_dir = tmp_path / "organized"
        target_dir.mkdir()
        
        target_paths = MediaPaths(
            video_path=target_dir / "artist" / "title.mp4",
            nfo_path=target_dir / "artist" / "title.nfo",
        )
        
        result = await file_manager.move_video_atomic(
            video_id=123,
            source_video_path=source_file,
            target_paths=target_paths,
            repository=mock_repository,
            dry_run=True,
        )
        
        # Source should still exist
        assert source_file.exists()
        
        # Target should NOT exist
        assert not target_paths.video_path.exists()
        
        # Repository should NOT be updated
        mock_repository.update_video.assert_not_called()

    @pytest.mark.asyncio
    async def test_move_source_not_found(self, file_manager, mock_repository, tmp_path):
        """Test error when source doesn't exist."""
        non_existent = tmp_path / "not_there.mp4"
        target_paths = MediaPaths(
            video_path=tmp_path / "target.mp4",
            nfo_path=tmp_path / "target.nfo",
        )
        
        with pytest.raises(FMFileNotFoundError):
            await file_manager.move_video_atomic(
                video_id=123,
                source_video_path=non_existent,
                target_paths=target_paths,
                repository=mock_repository,
            )

    @pytest.mark.asyncio
    async def test_move_target_exists(self, file_manager, source_file, mock_repository, tmp_path):
        """Test error when target already exists."""
        target_file = tmp_path / "existing.mp4"
        target_file.write_text("already here")
        
        target_paths = MediaPaths(
            video_path=target_file,
            nfo_path=tmp_path / "target.nfo",
        )
        
        with pytest.raises(FMFileExistsError):
            await file_manager.move_video_atomic(
                video_id=123,
                source_video_path=source_file,
                target_paths=target_paths,
                repository=mock_repository,
            )

    @pytest.mark.asyncio
    async def test_move_with_nfo(self, file_manager, source_file, mock_repository, tmp_path):
        """Test moving video with NFO file."""
        source_nfo = source_file.with_suffix(".nfo")
        source_nfo.write_text("<musicvideo><title>Test</title></musicvideo>")
        
        target_dir = tmp_path / "organized"
        target_dir.mkdir()
        
        target_paths = MediaPaths(
            video_path=target_dir / "video.mp4",
            nfo_path=target_dir / "video.nfo",
        )
        
        await file_manager.move_video_atomic(
            video_id=123,
            source_video_path=source_file,
            target_paths=target_paths,
            repository=mock_repository,
            source_nfo_path=source_nfo,
        )
        
        # Both files should be moved
        assert not source_file.exists()
        assert not source_nfo.exists()
        assert target_paths.video_path.exists()
        assert target_paths.nfo_path.exists()

    @pytest.mark.asyncio
    async def test_rollback_on_db_failure(self, file_manager, source_file, tmp_path):
        """Test rollback when database update fails."""
        # Mock repository that fails on update
        mock_repo = MagicMock()
        mock_repo.update_video = AsyncMock(side_effect=Exception("DB error"))
        
        target_dir = tmp_path / "organized"
        target_dir.mkdir()
        
        target_paths = MediaPaths(
            video_path=target_dir / "video.mp4",
            nfo_path=target_dir / "video.nfo",
        )
        
        original_content = source_file.read_bytes()
        
        with pytest.raises(Exception, match="DB error"):
            await file_manager.move_video_atomic(
                video_id=123,
                source_video_path=source_file,
                target_paths=target_paths,
                repository=mock_repo,
            )
        
        # Source should be restored
        assert source_file.exists()
        assert source_file.read_bytes() == original_content
        
        # Target should be removed
        assert not target_paths.video_path.exists()


class TestSoftDelete:
    """Tests for soft_delete method."""

    @pytest_asyncio.fixture
    async def file_manager(self, tmp_path):
        """Create file manager instance."""
        config = TrashConfig(trash_dir=".trash")
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        return FileManager(config, library_dir=library_dir, config_dir=config_dir)

    @pytest_asyncio.fixture
    async def video_file(self, tmp_path):
        """Create a video file."""
        video = tmp_path / "media" / "video.mp4"
        video.parent.mkdir(parents=True)
        video.write_text("video content")
        return video

    @pytest_asyncio.fixture
    async def mock_repository(self):
        """Create mock repository."""
        repo = MagicMock()
        repo.delete_video = AsyncMock()
        repo.update_video = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_soft_delete_moves_to_trash(self, file_manager, video_file, mock_repository, tmp_path):
        """Test soft delete moves file to trash."""
        trash_path = await file_manager.soft_delete(
            video_id=123,
            video_path=video_file,
            repository=mock_repository,
        )
        
        # Original should be gone
        assert not video_file.exists()
        
        # Trash file should exist
        assert trash_path.exists()
        assert ".trash" in str(trash_path)
        
        # Repository methods should be called
        mock_repository.delete_video.assert_called_once_with(123)
        mock_repository.update_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_soft_delete_file_not_found(self, file_manager, mock_repository, tmp_path):
        """Test error when file doesn't exist."""
        non_existent = tmp_path / "not_here.mp4"
        
        with pytest.raises(FMFileNotFoundError):
            await file_manager.soft_delete(
                video_id=123,
                video_path=non_existent,
                repository=mock_repository,
            )


class TestRestore:
    """Tests for restore method."""

    @pytest_asyncio.fixture
    async def file_manager(self, tmp_path):
        """Create file manager instance."""
        config = TrashConfig(trash_dir=".trash")
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        return FileManager(config, library_dir=library_dir, config_dir=config_dir)

    @pytest_asyncio.fixture
    async def trash_file(self, tmp_path):
        """Create a file in trash."""
        trash_dir = tmp_path / ".trash" / "media"
        trash_dir.mkdir(parents=True)
        trash_file = trash_dir / "video.mp4"
        trash_file.write_text("trashed content")
        return trash_file

    @pytest_asyncio.fixture
    async def mock_repository(self):
        """Create mock repository."""
        repo = MagicMock()
        repo.update_video = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_restore_success(self, file_manager, trash_file, mock_repository, tmp_path):
        """Test successful restore."""
        restore_path = tmp_path / "restored" / "video.mp4"
        
        result = await file_manager.restore(
            video_id=123,
            trash_video_path=trash_file,
            restore_path=restore_path,
            repository=mock_repository,
        )
        
        # Trash should be empty
        assert not trash_file.exists()
        
        # Restore target should exist
        assert restore_path.exists()
        assert result == restore_path
        
        # Repository should be updated
        mock_repository.update_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_file_not_found(self, file_manager, mock_repository, tmp_path):
        """Test error when trash file doesn't exist."""
        with pytest.raises(FMFileNotFoundError):
            await file_manager.restore(
                video_id=123,
                trash_video_path=tmp_path / "not_in_trash.mp4",
                restore_path=tmp_path / "restore.mp4",
                repository=mock_repository,
            )

    @pytest.mark.asyncio
    async def test_restore_target_exists(self, file_manager, trash_file, mock_repository, tmp_path):
        """Test error when restore target exists."""
        existing = tmp_path / "existing.mp4"
        existing.write_text("already here")
        
        with pytest.raises(FMFileExistsError):
            await file_manager.restore(
                video_id=123,
                trash_video_path=trash_file,
                restore_path=existing,
                repository=mock_repository,
            )


class TestHardDelete:
    """Tests for hard_delete method."""

    @pytest_asyncio.fixture
    async def file_manager(self, tmp_path):
        """Create file manager instance."""
        config = TrashConfig()
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        return FileManager(config, library_dir=library_dir, config_dir=config_dir)

    @pytest_asyncio.fixture
    async def video_file(self, tmp_path):
        """Create a video file."""
        video = tmp_path / "video.mp4"
        video.write_text("video content")
        return video

    @pytest_asyncio.fixture
    async def mock_repository(self):
        """Create mock repository."""
        repo = MagicMock()
        repo.hard_delete_video = AsyncMock()
        return repo

    @pytest.mark.asyncio
    async def test_hard_delete_removes_file(self, file_manager, video_file, mock_repository):
        """Test hard delete removes file from disk."""
        await file_manager.hard_delete(
            video_id=123,
            video_path=video_file,
            repository=mock_repository,
        )
        
        # File should be gone
        assert not video_file.exists()
        
        # Repository should be updated
        mock_repository.hard_delete_video.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_hard_delete_with_nfo(self, file_manager, video_file, mock_repository, tmp_path):
        """Test hard delete removes NFO file too."""
        nfo_file = video_file.with_suffix(".nfo")
        nfo_file.write_text("<nfo>content</nfo>")
        
        await file_manager.hard_delete(
            video_id=123,
            video_path=video_file,
            repository=mock_repository,
            nfo_path=nfo_file,
        )
        
        assert not video_file.exists()
        assert not nfo_file.exists()


class TestFindDuplicates:
    """Tests for duplicate detection methods."""

    @pytest_asyncio.fixture
    async def file_manager(self, tmp_path):
        """Create file manager instance."""
        config = TrashConfig()
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        return FileManager(config, library_dir=library_dir, config_dir=config_dir)

    @pytest.mark.asyncio
    async def test_find_duplicates_by_hash_no_hash(self, file_manager, tmp_path):
        """Test finding duplicates when source has no hash."""
        # Mock repository
        mock_repo = MagicMock()
        mock_repo._connection = MagicMock()
        mock_repo.get_video_by_id = AsyncMock(return_value={
            "id": 1,
            "title": "Test",
            "file_hash": None,
            "video_file_path": None,
        })
        
        duplicates = await file_manager.find_duplicates_by_hash(1, mock_repo)
        
        # No hash and no file path - should return empty
        assert duplicates == []

    @pytest.mark.asyncio
    async def test_find_duplicates_by_metadata(self, file_manager):
        """Test finding duplicates by metadata."""
        # Mock repository with duplicate
        mock_cursor = MagicMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            {
                "id": 2,
                "title": "test song",
                "artist": "test artist",
                "year": 2020,
                "video_file_path": "/path/to/video.mp4",
            }
        ])
        
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        
        mock_repo = MagicMock()
        mock_repo._connection = mock_conn
        mock_repo.get_video_by_id = AsyncMock(return_value={
            "id": 1,
            "title": "Test Song",  # Different case
            "artist": "Test Artist",
            "year": 2020,
        })
        
        duplicates = await file_manager.find_duplicates_by_metadata(1, mock_repo)
        
        # Should find the duplicate (case insensitive match)
        assert len(duplicates) == 1
        assert duplicates[0].video_id == 2
        assert duplicates[0].match_type == "metadata"
        assert duplicates[0].confidence >= 0.7


class TestVerifyLibrary:
    """Tests for library verification."""

    @pytest_asyncio.fixture
    async def file_manager(self, tmp_path):
        """Create file manager instance."""
        config = TrashConfig(trash_dir=".trash")
        library_dir = tmp_path / "music_videos"
        config_dir = tmp_path / "config"
        return FileManager(config, library_dir=library_dir, config_dir=config_dir)

    @pytest.mark.asyncio
    async def test_verify_finds_missing_files(self, file_manager, tmp_path):
        """Test verification finds missing files."""
        # Mock repository with video pointing to non-existent file
        mock_query = MagicMock()
        mock_query.execute = AsyncMock(return_value=[
            {
                "id": 1,
                "title": "Test",
                "video_file_path": str(tmp_path / "missing.mp4"),
                "nfo_file_path": None,
            }
        ])
        
        mock_repo = MagicMock()
        mock_repo.query = MagicMock(return_value=mock_query)
        
        report = await file_manager.verify_library(mock_repo, scan_orphans=False)
        
        assert report.videos_checked == 1
        assert report.missing_files == 1
        assert len(report.issues) == 1
        assert report.issues[0].issue_type == "missing_file"

    @pytest.mark.asyncio
    async def test_verify_finds_orphaned_files(self, file_manager, tmp_path):
        """Test verification finds orphaned files."""
        # Create an orphaned video file in the library_dir (not tmp_path root)
        library_dir = tmp_path / "music_videos"
        library_dir.mkdir(parents=True, exist_ok=True)
        orphan = library_dir / "orphan.mp4"
        orphan.write_text("orphan content")
        
        # Mock repository with no videos
        mock_query = MagicMock()
        mock_query.execute = AsyncMock(return_value=[])
        
        mock_repo = MagicMock()
        mock_repo.query = MagicMock(return_value=mock_query)
        
        report = await file_manager.verify_library(mock_repo, scan_orphans=True)
        
        assert report.orphaned_files == 1
        assert any(i.issue_type == "orphaned_file" for i in report.issues)


class TestLibraryReport:
    """Tests for LibraryReport class."""

    def test_add_issue(self):
        """Test adding issues to report."""
        report = LibraryReport()
        
        report.add_issue(LibraryIssue(
            issue_type="missing_file",
            video_id=1,
            path="/path/to/file.mp4",
            message="File not found",
        ))
        
        assert report.missing_files == 1
        assert len(report.issues) == 1

    def test_to_dict(self):
        """Test serialization to dict."""
        report = LibraryReport()
        report.videos_checked = 10
        report.files_scanned = 20
        report.add_issue(LibraryIssue(
            issue_type="orphaned_file",
            video_id=None,
            path="/orphan.mp4",
            message="Not in DB",
        ))
        
        data = report.to_dict()
        
        assert data["videos_checked"] == 10
        assert data["files_scanned"] == 20
        assert data["orphaned_files"] == 1
        assert data["total_issues"] == 1
        assert len(data["issues"]) == 1


class TestDuplicateCandidate:
    """Tests for DuplicateCandidate class."""

    def test_to_dict(self):
        """Test serialization to dict."""
        candidate = DuplicateCandidate(
            video_id=123,
            video_data={
                "title": "Test Song",
                "artist": "Test Artist",
                "video_file_path": "/path/to/file.mp4",
                "file_hash": "abc123",
            },
            match_type="hash",
            confidence=1.0,
        )
        
        data = candidate.to_dict()
        
        assert data["video_id"] == 123
        assert data["match_type"] == "hash"
        assert data["confidence"] == 1.0
        assert data["title"] == "Test Song"
        assert data["artist"] == "Test Artist"
