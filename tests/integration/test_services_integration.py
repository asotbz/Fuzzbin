"""Integration tests for service layer.

These tests verify the full integration between:
- Services (VideoService, ImportService, SearchService)
- Repository (VideoRepository with real SQLite database)
- FileManager (with real filesystem operations)

Unlike unit tests which mock dependencies, these tests use real components
to verify end-to-end functionality.
"""

import asyncio
import shutil
from pathlib import Path
from typing import AsyncGenerator, Dict, Any

import pytest
import pytest_asyncio

from fuzzbin.common.config import DatabaseConfig, FileManagerConfig, ThumbnailConfig
from fuzzbin.core.db import VideoRepository
from fuzzbin.core.file_manager import FileManager
from fuzzbin.services import (
    VideoService,
    ImportService,
    SearchService,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from fuzzbin.services.video_service import (
    OrganizeResult,
    DeleteResult,
    RestoreResult,
    DuplicatesResult,
    VideoWithRelationships,
)
from fuzzbin.services.search_service import (
    SearchResults,
    FacetedSearchResults,
    SearchSuggestions,
)


# ==================== Fixtures ====================


@pytest.fixture
def test_workspace(tmp_path: Path) -> Path:
    """Create a test workspace directory structure."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create standard directories
    (workspace / "media").mkdir()
    (workspace / "trash").mkdir()
    (workspace / "thumbnails").mkdir()
    (workspace / "organized").mkdir()

    return workspace


@pytest.fixture
def database_config(test_workspace: Path) -> DatabaseConfig:
    """Create database config pointing to test workspace."""
    return DatabaseConfig(
        database_path=str(test_workspace / "test.db"),
        enable_wal_mode=False,  # Disable WAL for tests
        connection_timeout=30,
        backup_dir=str(test_workspace / "backups"),
    )


@pytest.fixture
def file_manager_config(test_workspace: Path) -> FileManagerConfig:
    """Create FileManager config for test workspace."""
    return FileManagerConfig(
        trash_dir="trash",  # Relative to library_dir
        hash_algorithm="sha256",
        enable_hash_verification=True,
        organize_pattern="{artist}/{album}/{title}.{ext}",
    )


@pytest.fixture
def thumbnail_config(test_workspace: Path) -> ThumbnailConfig:
    """Create thumbnail config for tests."""
    return ThumbnailConfig(
        cache_dir="thumbnails",  # Relative to config_dir
        default_timestamp=5.0,
        width=320,
        height=180,
    )


@pytest_asyncio.fixture
async def repository(database_config: DatabaseConfig) -> AsyncGenerator[VideoRepository, None]:
    """Create a real VideoRepository with migrations applied."""
    repo = await VideoRepository.from_config(database_config)
    yield repo
    await repo.close()


@pytest.fixture
def file_manager(
    test_workspace: Path,
    file_manager_config: FileManagerConfig,
    thumbnail_config: ThumbnailConfig,
) -> FileManager:
    """Create a real FileManager for tests."""
    return FileManager(
        config=file_manager_config,
        library_dir=test_workspace / "media",
        config_dir=test_workspace / "config",
        thumbnail_config=thumbnail_config,
    )


@pytest_asyncio.fixture
async def video_service(
    repository: VideoRepository,
    file_manager: FileManager,
) -> VideoService:
    """Create VideoService with real dependencies."""
    return VideoService(
        repository=repository,
        file_manager=file_manager,
    )


@pytest_asyncio.fixture
async def search_service(repository: VideoRepository) -> SearchService:
    """Create SearchService with real repository."""
    return SearchService(repository=repository)


@pytest_asyncio.fixture
async def import_service(repository: VideoRepository) -> ImportService:
    """Create ImportService with real repository."""
    return ImportService(repository=repository)


def create_test_video_file(
    workspace: Path,
    filename: str = "test_video.mp4",
    content: bytes = b"fake video content",
) -> Path:
    """Create a test video file in the workspace."""
    video_path = workspace / "media" / filename
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(content)
    return video_path


def create_test_nfo_file(
    directory: Path,
    filename: str = "test_video.nfo",
    title: str = "Test Song",
    artist: str = "Test Artist",
) -> Path:
    """Create a test NFO file in the specified directory.

    Args:
        directory: Directory to create the file in
        filename: NFO filename
        title: Video title
        artist: Artist name

    Returns:
        Path to the created NFO file
    """
    nfo_path = directory / filename
    nfo_path.parent.mkdir(parents=True, exist_ok=True)
    nfo_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<musicvideo>
    <title>{title}</title>
    <artist>{artist}</artist>
    <album>Test Album</album>
    <year>2023</year>
</musicvideo>
"""
    nfo_path.write_text(nfo_content)
    return nfo_path


# ==================== VideoService Integration Tests ====================


class TestVideoServiceCRUDIntegration:
    """Integration tests for VideoService CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_and_retrieve_video(
        self, video_service: VideoService, repository: VideoRepository
    ):
        """Test creating and retrieving a video through the service."""
        # Create video - returns VideoWithRelationships
        result = await video_service.create(
            title="Smells Like Teen Spirit",
            artist="Nirvana",
            album="Nevermind",
            year=1991,
        )

        assert isinstance(result, VideoWithRelationships)
        assert result.id > 0
        assert result.title == "Smells Like Teen Spirit"

        # Retrieve video by ID
        video = await video_service.get_by_id(result.id)

        assert video["id"] == result.id
        assert video["title"] == "Smells Like Teen Spirit"
        assert video["artist"] == "Nirvana"
        assert video["album"] == "Nevermind"
        assert video["year"] == 1991

    @pytest.mark.asyncio
    async def test_get_video_not_found_raises(self, video_service: VideoService):
        """Test that getting a non-existent video raises NotFoundError."""
        with pytest.raises(NotFoundError) as exc_info:
            await video_service.get_by_id(99999)

        assert exc_info.value.resource_type == "video"
        assert exc_info.value.resource_id == 99999

    @pytest.mark.asyncio
    async def test_get_with_relationships(
        self, video_service: VideoService, repository: VideoRepository
    ):
        """Test retrieving video with full relationship data."""
        # Create video
        result = await video_service.create(
            title="Come As You Are",
            artist="Nirvana",
            album="Nevermind",
            year=1991,
        )
        video_id = result.id

        # Create and link artist
        artist_id = await repository.upsert_artist(name="Nirvana")
        await repository.link_video_artist(video_id, artist_id, role="primary")

        # Create and link tag
        tag_id = await repository.upsert_tag("grunge")
        await repository.add_video_tag(video_id, tag_id)

        # Retrieve with relationships
        video_with_rels = await video_service.get_with_relationships(video_id)

        assert isinstance(video_with_rels, VideoWithRelationships)
        assert video_with_rels.id == video_id
        assert video_with_rels.title == "Come As You Are"
        assert len(video_with_rels.artists) >= 1
        assert len(video_with_rels.tags) >= 1
        assert any(a["name"] == "Nirvana" for a in video_with_rels.artists)
        assert any(t["name"] == "grunge" for t in video_with_rels.tags)

    @pytest.mark.asyncio
    async def test_update_video(self, video_service: VideoService):
        """Test updating video metadata."""
        # Create video
        result = await video_service.create(
            title="Heart Shaped Box",
            artist="Nirvana",
        )
        video_id = result.id

        # Update
        await video_service.update(
            video_id,
            album="In Utero",
            year=1993,
            director="Anton Corbijn",
        )

        # Verify
        video = await video_service.get_by_id(video_id)
        assert video["album"] == "In Utero"
        assert video["year"] == 1993
        assert video["director"] == "Anton Corbijn"

    @pytest.mark.asyncio
    async def test_delete_video_soft(self, video_service: VideoService):
        """Test soft deleting a video."""
        result = await video_service.create(title="Test Delete", artist="Test")
        video_id = result.id

        # Soft delete
        await video_service.delete(video_id)

        # Should not find with default query
        with pytest.raises(NotFoundError):
            await video_service.get_by_id(video_id)

        # Should find with include_deleted
        video = await video_service.get_by_id(video_id, include_deleted=True)
        assert video["is_deleted"] == 1  # SQLite stores booleans as integers

    @pytest.mark.asyncio
    async def test_restore_video(self, video_service: VideoService):
        """Test restoring a soft-deleted video."""
        result = await video_service.create(title="Test Restore", artist="Test")
        video_id = result.id

        # Soft delete then restore
        await video_service.delete(video_id)
        await video_service.restore(video_id)

        # Should be findable again
        video = await video_service.get_by_id(video_id)
        assert video["is_deleted"] == 0  # SQLite stores booleans as integers


class TestVideoServiceStatusIntegration:
    """Integration tests for video status management."""

    @pytest.mark.asyncio
    async def test_update_status(self, video_service: VideoService, repository: VideoRepository):
        """Test updating video status with history tracking."""
        result = await video_service.create(title="Status Test", artist="Test")
        video_id = result.id

        # Update status
        await video_service.update_status(
            video_id,
            new_status="downloaded",
            reason="File downloaded successfully",
        )

        # Verify status
        video = await video_service.get_by_id(video_id)
        assert video["status"] == "downloaded"

        # Verify history was recorded
        history = await repository.get_status_history(video_id)
        assert len(history) >= 1
        assert any(h["new_status"] == "downloaded" for h in history)

    @pytest.mark.asyncio
    async def test_query_videos_with_filters(
        self, video_service: VideoService, repository: VideoRepository
    ):
        """Test querying videos with various filters through repository."""
        # Create test data
        await video_service.create(title="Song A", artist="Artist 1", status="discovered")
        await video_service.create(title="Song B", artist="Artist 1", status="downloaded")
        await video_service.create(title="Song C", artist="Artist 2", status="discovered")

        # Query by status using repository (VideoService doesn't have list method)
        query = repository.query().where_status("discovered")
        results = await query.execute()
        assert all(v["status"] == "discovered" for v in results)
        assert len(results) >= 2

        # Query by artist
        query = repository.query().where_artist("Artist 1")
        results = await query.execute()
        assert all(v["artist"] == "Artist 1" for v in results)
        assert len(results) >= 2


class TestVideoServiceExistenceIntegration:
    """Integration tests for video existence checking."""

    @pytest.mark.asyncio
    async def test_check_video_exists_by_title_artist(
        self, video_service: VideoService
    ):
        """Test checking if video exists by title/artist combination."""
        # Create video
        await video_service.create(title="Lithium", artist="Nirvana")

        # Check exists
        exists = await video_service.exists(
            title="Lithium",
            artist="Nirvana",
        )
        assert exists is True

        # Check non-existent
        exists = await video_service.exists(
            title="Nonexistent",
            artist="Nobody",
        )
        assert exists is False

    @pytest.mark.asyncio
    async def test_find_by_external_id_youtube(
        self, video_service: VideoService
    ):
        """Test finding video by YouTube ID."""
        # Create video with YouTube ID
        await video_service.create(
            title="Test",
            artist="Test",
            youtube_id="dQw4w9WgXcQ",
        )

        # Find by YouTube ID
        video = await video_service.find_by_external_id(youtube_id="dQw4w9WgXcQ")
        assert video is not None
        assert video["youtube_id"] == "dQw4w9WgXcQ"

        # Non-existent
        video = await video_service.find_by_external_id(youtube_id="nonexistent")
        assert video is None

    @pytest.mark.asyncio
    async def test_find_by_external_id_imvdb(
        self, video_service: VideoService
    ):
        """Test finding video by IMVDb ID."""
        await video_service.create(
            title="Test",
            artist="Test",
            imvdb_video_id="12345",
        )

        video = await video_service.find_by_external_id(imvdb_video_id="12345")
        assert video is not None
        assert video["imvdb_video_id"] == "12345"


class TestVideoServiceFileOpsIntegration:
    """Integration tests for file operations through VideoService."""

    @pytest.mark.asyncio
    async def test_delete_files_soft(
        self,
        video_service: VideoService,
        test_workspace: Path,
    ):
        """Test soft-deleting video files moves them to trash."""
        # Create video file
        video_path = create_test_video_file(test_workspace, "delete_test.mp4")

        # Create video record
        result = await video_service.create(
            title="Delete Test",
            artist="Test",
            video_file_path=str(video_path),
        )
        video_id = result.id

        # Soft delete
        delete_result = await video_service.delete_files(video_id, hard_delete=False)

        assert isinstance(delete_result, DeleteResult)
        assert delete_result.deleted is True
        assert delete_result.hard_delete is False
        assert delete_result.trash_path is not None

        # Original file should be gone
        assert not video_path.exists()

        # File should be in trash
        trash_path = Path(delete_result.trash_path)
        assert trash_path.exists()

    @pytest.mark.asyncio
    async def test_delete_files_hard(
        self,
        video_service: VideoService,
        test_workspace: Path,
    ):
        """Test hard-deleting video files permanently removes them."""
        video_path = create_test_video_file(test_workspace, "hard_delete_test.mp4")

        result = await video_service.create(
            title="Hard Delete Test",
            artist="Test",
            video_file_path=str(video_path),
        )
        video_id = result.id

        delete_result = await video_service.delete_files(video_id, hard_delete=True)

        assert delete_result.deleted is True
        assert delete_result.hard_delete is True
        assert delete_result.trash_path is None

        # File should be permanently gone
        assert not video_path.exists()

    @pytest.mark.asyncio
    async def test_restore_files_from_trash(
        self,
        video_service: VideoService,
        test_workspace: Path,
    ):
        """Test restoring files from trash."""
        video_path = create_test_video_file(test_workspace, "restore_test.mp4")
        original_path = str(video_path)

        result = await video_service.create(
            title="Restore Test",
            artist="Test",
            video_file_path=original_path,
        )
        video_id = result.id

        # Soft delete first
        await video_service.delete_files(video_id, hard_delete=False)

        # Restore
        restore_result = await video_service.restore_files(video_id)

        assert isinstance(restore_result, RestoreResult)
        assert restore_result.restored is True
        assert restore_result.restored_path is not None

        # File should be back
        restored_path = Path(restore_result.restored_path)
        assert restored_path.exists()


class TestVideoServiceDuplicatesIntegration:
    """Integration tests for duplicate detection."""

    @pytest.mark.asyncio
    async def test_find_duplicates_by_metadata(
        self,
        video_service: VideoService,
    ):
        """Test finding duplicates by matching title/artist."""
        # Create two videos with same title/artist
        result1 = await video_service.create(
            title="Duplicate Song",
            artist="Same Artist",
            album="Album 1",
        )
        video1_id = result1.id
        result2 = await video_service.create(
            title="Duplicate Song",
            artist="Same Artist",
            album="Album 2",
        )
        video2_id = result2.id

        # Find duplicates of first video
        result = await video_service.find_duplicates(video1_id, method="metadata")

        assert isinstance(result, DuplicatesResult)
        assert result.video_id == video1_id
        # Should find video2 as a duplicate
        duplicate_ids = [d.video_id for d in result.duplicates]
        assert video2_id in duplicate_ids

    @pytest.mark.asyncio
    async def test_find_duplicates_by_hash(
        self,
        video_service: VideoService,
        test_workspace: Path,
    ):
        """Test finding duplicates by file hash."""
        # Create two videos with same file content - hash will be computed
        content = b"identical video content for duplicate test"
        video1_path = create_test_video_file(test_workspace, "dup1.mp4", content)
        video2_path = create_test_video_file(test_workspace, "dup2.mp4", content)

        result1 = await video_service.create(
            title="Video 1",
            artist="Artist",
            video_file_path=str(video1_path),
        )
        video1_id = result1.id

        result2 = await video_service.create(
            title="Video 2",
            artist="Artist",
            video_file_path=str(video2_path),
        )
        video2_id = result2.id

        # Pre-compute hash for video2 so it's in the DB
        # (find_duplicates only computes for video1 if missing)
        file_manager = await video_service._get_file_manager()
        hash2 = await file_manager.compute_file_hash(video2_path)
        await video_service.repository.update_video(video2_id, file_checksum=hash2)

        result = await video_service.find_duplicates(video1_id, method="hash")

        duplicate_ids = [d.video_id for d in result.duplicates]
        assert video2_id in duplicate_ids

    @pytest.mark.asyncio
    async def test_resolve_duplicates(
        self,
        video_service: VideoService,
    ):
        """Test resolving duplicates by keeping one and removing others."""
        # Create duplicates
        keep_result = await video_service.create(
            title="Keep This",
            artist="Artist",
        )
        keep_id = keep_result.id
        remove1_result = await video_service.create(
            title="Remove This 1",
            artist="Artist",
        )
        remove1_id = remove1_result.id
        remove2_result = await video_service.create(
            title="Remove This 2",
            artist="Artist",
        )
        remove2_id = remove2_result.id

        # Resolve - keep one, remove others
        result = await video_service.resolve_duplicates(
            keep_video_id=keep_id,
            remove_video_ids=[remove1_id, remove2_id],
            hard_delete=False,
        )

        assert result.kept_video_id == keep_id
        assert result.removed_count == 2
        assert remove1_id in result.removed_video_ids
        assert remove2_id in result.removed_video_ids

        # Kept video should still exist
        video = await video_service.get_by_id(keep_id)
        assert video is not None

        # Removed videos should be deleted
        with pytest.raises(NotFoundError):
            await video_service.get_by_id(remove1_id)


# ==================== SearchService Integration Tests ====================


class TestSearchServiceIntegration:
    """Integration tests for SearchService."""

    @pytest.mark.asyncio
    async def test_search_videos_by_text(
        self,
        search_service: SearchService,
        repository: VideoRepository,
    ):
        """Test full-text search across video fields."""
        # Create test data
        await repository.create_video(
            title="Smells Like Teen Spirit",
            artist="Nirvana",
            album="Nevermind",
            genre="Grunge",
        )
        await repository.create_video(
            title="Come As You Are",
            artist="Nirvana",
            album="Nevermind",
            genre="Grunge",
        )
        await repository.create_video(
            title="Basket Case",
            artist="Green Day",
            album="Dookie",
            genre="Punk",
        )

        # Search for Nirvana
        result = await search_service.search_videos("Nirvana")

        assert result["total"] >= 2
        titles = [v["title"] for v in result["items"]]
        assert "Smells Like Teen Spirit" in titles
        assert "Come As You Are" in titles
        assert "Basket Case" not in titles

    @pytest.mark.asyncio
    async def test_search_all_entities(
        self,
        search_service: SearchService,
        repository: VideoRepository,
    ):
        """Test cross-entity search returning videos, artists, etc."""
        # Create video
        await repository.create_video(
            title="November Rain",
            artist="Guns N' Roses",
        )

        # Create artist
        await repository.upsert_artist(
            name="Guns N' Roses",
        )

        # Search
        result = await search_service.search_all("Guns")

        assert isinstance(result, SearchResults)
        assert result.total >= 1
        # Should find matches in videos or artists
        all_results = result.videos + result.artists
        assert len(all_results) >= 1

    @pytest.mark.asyncio
    async def test_get_suggestions(
        self,
        search_service: SearchService,
        repository: VideoRepository,
    ):
        """Test autocomplete suggestions."""
        # Create test data
        await repository.create_video(title="Smells Like Teen Spirit", artist="Nirvana")
        await repository.create_video(title="Come As You Are", artist="Nirvana")
        await repository.create_video(title="Something In The Way", artist="Nirvana")

        # Get suggestions
        suggestions = await search_service.get_suggestions("Smell")

        assert isinstance(suggestions, SearchSuggestions)
        assert "Smells Like Teen Spirit" in suggestions.titles

    @pytest.mark.asyncio
    async def test_faceted_search(
        self,
        search_service: SearchService,
        repository: VideoRepository,
    ):
        """Test faceted search with filter counts."""
        # Create diverse test data
        await repository.create_video(title="Song 1", artist="Artist A", year=1991, genre="Rock")
        await repository.create_video(title="Song 2", artist="Artist A", year=1991, genre="Rock")
        await repository.create_video(title="Song 3", artist="Artist B", year=1992, genre="Pop")
        await repository.create_video(title="Song 4", artist="Artist C", year=1993, genre="Pop")

        # Faceted search
        result = await search_service.search_with_facets(
            query="Song",
            page=1,
            page_size=20,
        )

        assert isinstance(result, FacetedSearchResults)
        assert result.total >= 4

        # Should have facets for filtering
        facet_names = [f.name for f in result.facets]
        # Common facets: year, genre, artist
        assert len(facet_names) >= 1


class TestSearchServiceCachedIntegration:
    """Integration tests for cached search operations."""

    @pytest.mark.asyncio
    async def test_get_stats_cached(
        self,
        search_service: SearchService,
        repository: VideoRepository,
    ):
        """Test that stats are cached."""
        # Create some data
        await repository.create_video(title="Test 1", artist="Artist")
        await repository.create_video(title="Test 2", artist="Artist")

        # First call
        stats1 = await search_service.get_library_stats()

        # Second call should be cached
        stats2 = await search_service.get_library_stats()

        assert stats1 == stats2
        assert stats1["total_videos"] >= 2


# ==================== ImportService Integration Tests ====================


class TestImportServiceNFOIntegration:
    """Integration tests for NFO import workflow."""

    @pytest.mark.asyncio
    async def test_import_nfo_directory(
        self,
        import_service: ImportService,
        repository: VideoRepository,
        test_workspace: Path,
    ):
        """Test importing NFO files from a directory."""
        # Create test NFO files
        nfo_dir = test_workspace / "imports"
        nfo_dir.mkdir()

        create_test_nfo_file(
            nfo_dir,
            "video1.nfo",
            title="Song One",
            artist="Artist One",
        )
        create_test_nfo_file(
            nfo_dir,
            "video2.nfo",
            title="Song Two",
            artist="Artist Two",
        )

        # Import
        result = await import_service.import_nfo_directory(
            directory=nfo_dir,
            recursive=False,
        )

        assert result.total_files >= 2
        assert result.imported_count >= 2

        # Verify videos were created in database
        videos = await repository.query().execute()
        titles = [v["title"] for v in videos]
        assert "Song One" in titles
        assert "Song Two" in titles

    @pytest.mark.asyncio
    async def test_import_nfo_recursive(
        self,
        import_service: ImportService,
        test_workspace: Path,
    ):
        """Test recursive NFO import."""
        # Create nested directory structure
        imports_dir = test_workspace / "imports"
        subdir = imports_dir / "subdir"
        subdir.mkdir(parents=True)

        create_test_nfo_file(
            imports_dir,
            "root.nfo",
            title="Root Song",
            artist="Artist",
        )
        create_test_nfo_file(
            subdir,
            "nested.nfo",
            title="Nested Song",
            artist="Artist",
        )

        # Import recursively
        result = await import_service.import_nfo_directory(
            directory=imports_dir,
            recursive=True,
        )

        assert result.total_files >= 2
        assert result.imported_count >= 2

    @pytest.mark.asyncio
    async def test_import_nfo_skips_existing(
        self,
        import_service: ImportService,
        repository: VideoRepository,
        test_workspace: Path,
    ):
        """Test that import skips existing videos."""
        nfo_dir = test_workspace / "imports"
        nfo_dir.mkdir(exist_ok=True)

        create_test_nfo_file(
            nfo_dir,
            "existing.nfo",
            title="Existing Song",
            artist="Existing Artist",
        )

        # Pre-create video in database
        await repository.create_video(
            title="Existing Song",
            artist="Existing Artist",
        )

        # Import - should skip
        result = await import_service.import_nfo_directory(
            directory=nfo_dir,
            skip_existing=True,
        )

        assert result.skipped_count >= 1

    @pytest.mark.asyncio
    async def test_import_nfo_invalid_directory_raises(
        self, import_service: ImportService
    ):
        """Test that invalid directory raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await import_service.import_nfo_directory(
                directory=Path("/nonexistent/path")
            )

        assert exc_info.value.field == "directory"


# ==================== Cross-Service Integration Tests ====================


class TestCrossServiceIntegration:
    """Tests verifying interactions between multiple services."""

    @pytest.mark.asyncio
    async def test_import_then_search(
        self,
        import_service: ImportService,
        search_service: SearchService,
        test_workspace: Path,
    ):
        """Test that imported videos are searchable."""
        # Create and import NFO
        nfo_dir = test_workspace / "imports"
        nfo_dir.mkdir(exist_ok=True)

        create_test_nfo_file(
            nfo_dir,
            "searchable.nfo",
            title="Searchable Song",
            artist="Searchable Artist",
        )

        await import_service.import_nfo_directory(directory=nfo_dir)

        # Search for imported video
        result = await search_service.search_videos("Searchable")

        assert result["total"] >= 1
        assert any(v["title"] == "Searchable Song" for v in result["items"])

    @pytest.mark.asyncio
    async def test_video_service_search_service_consistency(
        self,
        video_service: VideoService,
        search_service: SearchService,
    ):
        """Test that VideoService and SearchService return consistent data."""
        # Create via VideoService
        result = await video_service.create(
            title="Consistency Test",
            artist="Test Artist",
            album="Test Album",
        )
        video_id = result.id

        # Get via VideoService
        video = await video_service.get_by_id(video_id)

        # Search via SearchService
        search_result = await search_service.search_videos("Consistency Test")

        # Should find the same video
        assert search_result["total"] >= 1
        found_video = next(
            (v for v in search_result["items"] if v["id"] == video_id),
            None,
        )
        assert found_video is not None
        assert found_video["title"] == video["title"]
        assert found_video["artist"] == video["artist"]

    @pytest.mark.asyncio
    async def test_delete_removes_from_search(
        self,
        video_service: VideoService,
        search_service: SearchService,
    ):
        """Test that deleted videos don't appear in search results."""
        # Create video
        result = await video_service.create(
            title="Delete Me From Search",
            artist="Test",
        )
        video_id = result.id

        # Verify it's searchable
        search_result = await search_service.search_videos("Delete Me From Search")
        assert search_result["total"] >= 1

        # Delete video
        await video_service.delete(video_id)

        # Should not appear in search anymore
        search_result = await search_service.search_videos("Delete Me From Search")
        found_ids = [v["id"] for v in search_result["items"]]
        assert video_id not in found_ids


# ==================== Error Handling Integration Tests ====================


class TestServiceErrorHandling:
    """Integration tests for error handling across services."""

    @pytest.mark.asyncio
    async def test_not_found_error_propagation(
        self,
        video_service: VideoService,
    ):
        """Test that NotFoundError is properly raised and contains context."""
        with pytest.raises(NotFoundError) as exc_info:
            await video_service.get_by_id(999999)

        error = exc_info.value
        assert error.resource_type == "video"
        assert error.resource_id == 999999
        assert "not found" in str(error.message).lower()

    @pytest.mark.asyncio
    async def test_validation_error_for_invalid_input(
        self,
        video_service: VideoService,
    ):
        """Test that invalid input raises ValidationError."""
        result = await video_service.create(title="Test", artist="Test")
        video_id = result.id

        # Try to delete files from video without file path
        with pytest.raises(ValidationError):
            await video_service.delete_files(video_id)

    @pytest.mark.asyncio
    async def test_concurrent_operations_are_safe(
        self,
        video_service: VideoService,
    ):
        """Test that concurrent service operations don't cause issues."""

        async def create_video(n: int) -> int:
            result = await video_service.create(
                title=f"Concurrent Video {n}",
                artist="Test",
            )
            return result.id

        # Create multiple videos concurrently
        tasks = [create_video(i) for i in range(10)]
        video_ids = await asyncio.gather(*tasks)

        # All should succeed
        assert len(video_ids) == 10
        assert len(set(video_ids)) == 10  # All unique IDs

        # All should be retrievable
        for video_id in video_ids:
            video = await video_service.get_by_id(video_id)
            assert video is not None


# ==================== Transaction Integration Tests ====================


class TestTransactionIntegration:
    """Integration tests for transactional operations."""

    @pytest.mark.asyncio
    async def test_create_video_with_relationships_atomic(
        self,
        video_service: VideoService,
        repository: VideoRepository,
    ):
        """Test that creating video with relationships is atomic."""
        # This should create video and link artist in one transaction
        result = await video_service.create_with_artists(
            title="Atomic Test",
            artists=[{"name": "Atomic Artist", "role": "primary"}],
            album="Atomic Album",
        )
        video_id = result.id

        # Verify video was created
        video = await video_service.get_by_id(video_id)
        assert video["title"] == "Atomic Test"

        # Verify artist was linked
        video_with_rels = await video_service.get_with_relationships(video_id)
        assert len(video_with_rels.artists) >= 1
        assert any(a["name"] == "Atomic Artist" for a in video_with_rels.artists)
