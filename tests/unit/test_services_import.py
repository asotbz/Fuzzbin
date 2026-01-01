"""Unit tests for ImportService."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from fuzzbin.services.import_service import ImportService, NFOImportResult, SpotifyImportResult
from fuzzbin.services.base import ServiceCallback, ServiceError, ValidationError


@pytest.fixture
def mock_repository():
    """Mock VideoRepository for testing."""
    repository = AsyncMock()
    repository.create_video = AsyncMock(return_value=1)
    repository.upsert_artist = AsyncMock(return_value=1)
    repository.link_video_artist = AsyncMock()

    # Transaction
    repository.transaction = MagicMock()
    repository.transaction.__aenter__ = AsyncMock()
    repository.transaction.__aexit__ = AsyncMock()

    return repository


@pytest.fixture
def mock_spotify_client():
    """Mock SpotifyClient for testing."""
    client = AsyncMock()
    client.get_playlist = AsyncMock(return_value=MagicMock(name="Test Playlist"))
    client.get_playlist_tracks = AsyncMock(return_value=[
        {"track": {"name": "Song 1", "artists": [{"name": "Artist 1"}]}},
        {"track": {"name": "Song 2", "artists": [{"name": "Artist 2"}]}},
    ])
    return client


@pytest.fixture
def import_service(mock_repository, mock_spotify_client):
    """Create ImportService instance for testing."""
    return ImportService(
        repository=mock_repository,
        spotify_client=mock_spotify_client,
    )


# Mock ImportResult dataclass for workflow results
@dataclass
class MockImportResult:
    """Mock ImportResult from workflow."""
    playlist_id: str = ""
    playlist_name: str = ""
    total_tracks: int = 0
    imported_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    failed_tracks: list = None
    duration_seconds: float = 0.0
    
    def __post_init__(self):
        if self.failed_tracks is None:
            self.failed_tracks = []


class TestNFOImport:
    """Tests for NFO directory import."""

    @pytest.mark.asyncio
    async def test_import_nfo_directory_validates_path(self, import_service):
        """Test that non-existent paths raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await import_service.import_nfo_directory(Path("/nonexistent/path"))

        assert exc_info.value.field == "directory"

    @pytest.mark.asyncio
    async def test_import_nfo_directory_success(self, import_service, tmp_path):
        """Test successful NFO directory import."""
        # Create temp NFO file
        nfo_file = tmp_path / "video.nfo"
        nfo_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<musicvideo>
    <title>Test Song</title>
    <artist>Test Artist</artist>
</musicvideo>
""")

        # Mock the NFOImporter class
        with patch("fuzzbin.services.import_service.NFOImporter") as MockImporter:
            mock_instance = MagicMock()
            # import_from_directory is async
            mock_result = MockImportResult(
                playlist_id="",
                playlist_name="",
                total_tracks=1,
                imported_count=1,
                skipped_count=0,
                failed_count=0,
            )
            # Return tuple (result, imported_videos) to match NFOImporter interface
            mock_instance.import_from_directory = AsyncMock(return_value=(mock_result, []))
            MockImporter.return_value = mock_instance

            result = await import_service.import_nfo_directory(tmp_path)

            assert isinstance(result, NFOImportResult)
            assert result.imported_count == 1
            mock_instance.import_from_directory.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_multiple_directories(self, import_service, tmp_path):
        """Test importing multiple NFO directories."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Create NFO files
        (dir1 / "video.nfo").write_text("<musicvideo><title>Test 1</title></musicvideo>")
        (dir2 / "video.nfo").write_text("<musicvideo><title>Test 2</title></musicvideo>")

        with patch("fuzzbin.services.import_service.NFOImporter") as MockImporter:
            mock_instance = MagicMock()
            mock_result = MockImportResult(
                total_tracks=1,
                imported_count=1,
            )
            # Return tuple (result, imported_videos) to match NFOImporter interface
            mock_instance.import_from_directory = AsyncMock(return_value=(mock_result, []))
            MockImporter.return_value = mock_instance

            results = await import_service.import_multiple_nfo_directories([dir1, dir2])

            assert isinstance(results, list)
            assert len(results) == 2
            assert mock_instance.import_from_directory.call_count == 2


class TestSpotifyImport:
    """Tests for Spotify playlist import."""

    @pytest.mark.asyncio
    async def test_import_spotify_validates_playlist_id(self, import_service):
        """Test that empty playlist_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            await import_service.import_spotify_playlist("")

        assert exc_info.value.field == "playlist_id"

    @pytest.mark.asyncio
    async def test_import_spotify_requires_client(self, mock_repository):
        """Test that missing Spotify client raises ValidationError."""
        service = ImportService(repository=mock_repository, spotify_client=None)

        with pytest.raises(ValidationError) as exc_info:
            await service.import_spotify_playlist("37i9dQZF1DXcBWIGoYBM5M")

        assert "Spotify client" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_import_spotify_success(self, import_service):
        """Test successful Spotify playlist import."""
        with patch("fuzzbin.services.import_service.SpotifyPlaylistImporter") as MockImporter:
            mock_instance = MagicMock()
            mock_result = MockImportResult(
                playlist_id="37i9dQZF1DXcBWIGoYBM5M",
                playlist_name="Test Playlist",
                total_tracks=2,
                imported_count=2,
            )
            mock_instance.import_playlist = AsyncMock(return_value=mock_result)
            MockImporter.return_value = mock_instance

            result = await import_service.import_spotify_playlist(
                playlist_id="37i9dQZF1DXcBWIGoYBM5M"
            )

            assert isinstance(result, SpotifyImportResult)
            assert result.total_tracks == 2
            assert result.imported_count == 2


class TestYouTubeSearch:
    """Tests for YouTube search import."""

    @pytest.mark.asyncio
    async def test_import_youtube_search_not_implemented(self, import_service):
        """Test that YouTube search is not yet implemented."""
        with pytest.raises(NotImplementedError):
            await import_service.import_youtube_search("music video", max_results=5)


class TestCallbackIntegration:
    """Tests for callback integration."""

    @pytest.mark.asyncio
    async def test_error_callback_on_failure(self, mock_repository, mock_spotify_client, tmp_path):
        """Test that failure callback is invoked on errors."""
        callback = MagicMock(spec=ServiceCallback)
        callback.on_failure = AsyncMock()
        callback.on_complete = AsyncMock()
        callback.on_progress = AsyncMock()

        # Create service with callback
        service = ImportService(
            repository=mock_repository,
            spotify_client=mock_spotify_client,
            callback=callback,
        )

        with patch("fuzzbin.services.import_service.NFOImporter") as MockImporter:
            mock_instance = MagicMock()
            mock_instance.import_from_directory = AsyncMock(side_effect=Exception("Import failed"))
            MockImporter.return_value = mock_instance

            # Create a valid temp dir
            nfo_file = tmp_path / "video.nfo"
            nfo_file.write_text("<musicvideo><title>Test</title></musicvideo>")

            with pytest.raises(ServiceError):
                await service.import_nfo_directory(tmp_path)

            callback.on_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_null_callback_is_safe(self, import_service, tmp_path):
        """Test that None callback doesn't cause errors."""
        nfo_file = tmp_path / "video.nfo"
        nfo_file.write_text("<musicvideo><title>Test</title></musicvideo>")

        with patch("fuzzbin.services.import_service.NFOImporter") as MockImporter:
            mock_instance = MagicMock()
            mock_result = MockImportResult(
                total_tracks=1,
                imported_count=1,
            )
            # Return tuple (result, imported_videos) to match NFOImporter interface
            mock_instance.import_from_directory = AsyncMock(return_value=(mock_result, []))
            MockImporter.return_value = mock_instance

            # Should not raise even without callback
            result = await import_service.import_nfo_directory(tmp_path)
            assert result.imported_count == 1
