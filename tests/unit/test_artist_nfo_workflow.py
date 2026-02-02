"""Tests for artist.nfo auto-creation during video organization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from fuzzbin.common.config import Config, OrganizerConfig, NFOConfig
from fuzzbin.parsers.artist_parser import ArtistNFOParser
from fuzzbin.parsers.models import ArtistNFO
from fuzzbin.tasks.handlers import _get_artist_directory_from_pattern
from fuzzbin.tasks.models import Job, JobType


class TestArtistDirectoryDetection:
    """Test artist directory detection from path patterns."""

    def test_pattern_with_artist_simple(self, tmp_path):
        """Test pattern with {artist} at root level."""
        pattern = "{artist}/{title}"
        video_path = tmp_path / "Nirvana" / "Smells Like Teen Spirit.mp4"
        root_path = tmp_path

        artist_dir = _get_artist_directory_from_pattern(pattern, video_path, root_path)

        assert artist_dir == tmp_path / "Nirvana"

    def test_pattern_with_artist_nested(self, tmp_path):
        """Test pattern with {artist} nested in directory structure."""
        pattern = "{genre}/{artist}/{year}/{title}"
        video_path = tmp_path / "Rock" / "Nirvana" / "1991" / "Smells Like Teen Spirit.mp4"
        root_path = tmp_path

        artist_dir = _get_artist_directory_from_pattern(pattern, video_path, root_path)

        assert artist_dir == tmp_path / "Rock" / "Nirvana"

    def test_pattern_without_artist(self, tmp_path):
        """Test pattern without {artist} returns None."""
        pattern = "{title}"
        video_path = tmp_path / "Smells Like Teen Spirit.mp4"
        root_path = tmp_path

        artist_dir = _get_artist_directory_from_pattern(pattern, video_path, root_path)

        assert artist_dir is None

    def test_pattern_with_artist_in_filename(self, tmp_path):
        """Test pattern with {artist} in filename (not directory) returns None."""
        pattern = "{title} - {artist}"
        video_path = tmp_path / "Smells Like Teen Spirit - Nirvana.mp4"
        root_path = tmp_path

        artist_dir = _get_artist_directory_from_pattern(pattern, video_path, root_path)

        # Pattern has no directory separator, so there's no artist directory
        assert artist_dir is None

    def test_pattern_complex_artist_position(self, tmp_path):
        """Test pattern with {artist} at various positions."""
        # Test first position
        pattern = "{artist}/{genre}/{title}"
        video_path = tmp_path / "Nirvana" / "Grunge" / "Smells Like Teen Spirit.mp4"
        artist_dir = _get_artist_directory_from_pattern(pattern, video_path, tmp_path)
        assert artist_dir == tmp_path / "Nirvana"

        # Test third position
        pattern = "{genre}/{year}/{artist}/{title}"
        video_path = tmp_path / "Rock" / "1991" / "Nirvana" / "Smells Like Teen Spirit.mp4"
        artist_dir = _get_artist_directory_from_pattern(pattern, video_path, tmp_path)
        assert artist_dir == tmp_path / "Rock" / "1991" / "Nirvana"


@pytest.mark.asyncio
class TestArtistNfoWorkflow:
    """Test artist.nfo creation and validation in organize workflow."""

    @pytest_asyncio.fixture
    async def mock_repository(self):
        """Create mock repository."""
        repo = AsyncMock()
        repo.get_video_by_id = AsyncMock(
            return_value={
                "id": 1,
                "title": "Smells Like Teen Spirit",
                "artist": "Nirvana",
                "album": "Nevermind",
                "year": 1991,
                "director": "Samuel Bayer",
                "genre": "Rock",
                "studio": "DGC",
            }
        )
        repo.get_video_artists = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "name": "Nirvana",
                    "role": "primary",
                    "position": 0,
                }
            ]
        )
        repo.update_video = AsyncMock()
        repo.get_artist_by_id = AsyncMock(
            return_value={
                "id": 1,
                "name": "Nirvana",
            }
        )
        return repo

    @pytest_asyncio.fixture
    async def mock_config(self, tmp_path):
        """Create mock config with artist directory pattern."""
        config = MagicMock(spec=Config)
        config.library_dir = tmp_path / "library"
        config.library_dir.mkdir(parents=True, exist_ok=True)
        config.organizer = OrganizerConfig(
            path_pattern="{artist}/{title}",
            normalize_filenames=False,
        )
        # Add nfo config for write_artist_nfo check
        config.nfo = NFOConfig()
        return config

    async def test_create_new_artist_nfo(self, mock_repository, mock_config, tmp_path):
        """Test creating new artist.nfo when it doesn't exist."""
        from fuzzbin.tasks.handlers import handle_import_organize

        # Create temp video file
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        temp_file = temp_dir / "video.mp4"
        temp_file.write_text("test video")

        # Create job
        job = Job(
            type=JobType.IMPORT_ORGANIZE,
            metadata={
                "video_id": 1,
                "temp_path": str(temp_file),
            },
        )

        with (
            patch("fuzzbin.get_repository", return_value=mock_repository),
            patch("fuzzbin.get_config", return_value=mock_config),
            patch("fuzzbin.tasks.handlers.get_job_queue") as mock_queue,
        ):
            mock_queue.return_value.submit = AsyncMock()

            # Run organize handler
            await handle_import_organize(job)

        # Verify artist.nfo was created
        artist_nfo_path = mock_config.library_dir / "Nirvana" / "artist.nfo"
        assert artist_nfo_path.exists()

        # Verify content
        parser = ArtistNFOParser()
        artist_nfo = parser.parse_file(artist_nfo_path)
        assert artist_nfo.name == "Nirvana"

    async def test_preserve_existing_artist_nfo_same_name(
        self, mock_repository, mock_config, tmp_path
    ):
        """Test preserving existing artist.nfo with same artist name."""
        from fuzzbin.tasks.handlers import handle_import_organize

        # Create temp video file
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        temp_file = temp_dir / "video.mp4"
        temp_file.write_text("test video")

        # Create existing artist.nfo
        artist_dir = mock_config.library_dir / "Nirvana"
        artist_dir.mkdir(parents=True, exist_ok=True)
        artist_nfo_path = artist_dir / "artist.nfo"
        parser = ArtistNFOParser()
        parser.write_file(ArtistNFO(name="Nirvana"), artist_nfo_path)

        # Record original modification time
        _original_mtime = artist_nfo_path.stat().st_mtime

        # Create job
        job = Job(
            type=JobType.IMPORT_ORGANIZE,
            metadata={
                "video_id": 1,
                "temp_path": str(temp_file),
            },
        )

        with (
            patch("fuzzbin.get_repository", return_value=mock_repository),
            patch("fuzzbin.get_config", return_value=mock_config),
            patch("fuzzbin.tasks.handlers.get_job_queue") as mock_queue,
        ):
            mock_queue.return_value.submit = AsyncMock()

            # Run organize handler
            await handle_import_organize(job)

        # Verify artist.nfo still exists and wasn't modified
        assert artist_nfo_path.exists()

        # Content should be the same
        artist_nfo = parser.parse_file(artist_nfo_path)
        assert artist_nfo.name == "Nirvana"

    async def test_update_existing_artist_nfo_different_name(
        self, mock_repository, mock_config, tmp_path
    ):
        """Test updating existing artist.nfo when artist name differs."""
        from fuzzbin.tasks.handlers import handle_import_organize

        # Create temp video file
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        temp_file = temp_dir / "video.mp4"
        temp_file.write_text("test video")

        # Create existing artist.nfo with different name
        artist_dir = mock_config.library_dir / "Nirvana"
        artist_dir.mkdir(parents=True, exist_ok=True)
        artist_nfo_path = artist_dir / "artist.nfo"
        parser = ArtistNFOParser()
        parser.write_file(ArtistNFO(name="Old Band Name"), artist_nfo_path)

        # Create job
        job = Job(
            type=JobType.IMPORT_ORGANIZE,
            metadata={
                "video_id": 1,
                "temp_path": str(temp_file),
            },
        )

        with (
            patch("fuzzbin.get_repository", return_value=mock_repository),
            patch("fuzzbin.get_config", return_value=mock_config),
            patch("fuzzbin.tasks.handlers.get_job_queue") as mock_queue,
        ):
            mock_queue.return_value.submit = AsyncMock()

            # Run organize handler
            await handle_import_organize(job)

        # Verify artist.nfo was updated
        assert artist_nfo_path.exists()
        artist_nfo = parser.parse_file(artist_nfo_path)
        assert artist_nfo.name == "Nirvana"

    async def test_skip_artist_nfo_when_no_artist_in_pattern(self, mock_repository, tmp_path):
        """Test skipping artist.nfo creation when pattern has no {artist}."""
        from fuzzbin.tasks.handlers import handle_import_organize

        # Config without {artist} in pattern
        config = MagicMock(spec=Config)
        config.library_dir = tmp_path / "library"
        config.library_dir.mkdir(parents=True, exist_ok=True)
        config.organizer = OrganizerConfig(
            path_pattern="{title}",  # No {artist}
            normalize_filenames=False,
        )

        # Create temp video file
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        temp_file = temp_dir / "video.mp4"
        temp_file.write_text("test video")

        # Create job
        job = Job(
            type=JobType.IMPORT_ORGANIZE,
            metadata={
                "video_id": 1,
                "temp_path": str(temp_file),
            },
        )

        with (
            patch("fuzzbin.get_repository", return_value=mock_repository),
            patch("fuzzbin.get_config", return_value=config),
            patch("fuzzbin.tasks.handlers.get_job_queue") as mock_queue,
        ):
            mock_queue.return_value.submit = AsyncMock()

            # Run organize handler
            await handle_import_organize(job)

        # Verify no artist.nfo was created
        artist_nfo_files = list(config.library_dir.rglob("artist.nfo"))
        assert len(artist_nfo_files) == 0

    async def test_error_when_no_primary_artist_with_artist_pattern(
        self, mock_repository, mock_config, tmp_path
    ):
        """Test error when video has no primary artist but pattern requires {artist}."""
        from fuzzbin.tasks.handlers import handle_import_organize

        # Mock repository to return no primary artists AND no artist field on video
        mock_repository.get_video_artists = AsyncMock(return_value=[])
        mock_repository.get_video_by_id = AsyncMock(
            return_value={
                "id": 1,
                "title": "Smells Like Teen Spirit",
                "artist": None,  # No artist field either
                "album": "Nevermind",
                "year": 1991,
                "director": "Samuel Bayer",
                "genre": "Rock",
                "studio": "DGC",
            }
        )

        # Create temp video file
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        temp_file = temp_dir / "video.mp4"
        temp_file.write_text("test video")

        # Create job
        job = Job(
            type=JobType.IMPORT_ORGANIZE,
            metadata={
                "video_id": 1,
                "temp_path": str(temp_file),
            },
        )

        with (
            patch("fuzzbin.get_repository", return_value=mock_repository),
            patch("fuzzbin.get_config", return_value=mock_config),
            patch("fuzzbin.tasks.handlers.get_job_queue") as mock_queue,
        ):
            mock_queue.return_value.submit = AsyncMock()

            # Should raise MissingFieldError because artist is required by pattern
            from fuzzbin.core.exceptions import MissingFieldError

            with pytest.raises(MissingFieldError, match="artist.*required by pattern"):
                await handle_import_organize(job)

        # Verify temp file was cleaned up
        assert not temp_file.exists()

    async def test_artist_nfo_creation_failure_fails_operation(
        self, mock_repository, mock_config, tmp_path
    ):
        """Test that artist.nfo creation failure fails the entire operation."""
        from fuzzbin.tasks.handlers import handle_import_organize

        # Create temp video file
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        temp_file = temp_dir / "video.mp4"
        temp_file.write_text("test video")

        # Make get_artist_by_id raise an error
        mock_repository.get_artist_by_id = AsyncMock(side_effect=Exception("Database error"))

        # Create job
        job = Job(
            type=JobType.IMPORT_ORGANIZE,
            metadata={
                "video_id": 1,
                "temp_path": str(temp_file),
            },
        )

        with (
            patch("fuzzbin.get_repository", return_value=mock_repository),
            patch("fuzzbin.get_config", return_value=mock_config),
            patch("fuzzbin.tasks.handlers.get_job_queue") as mock_queue,
        ):
            mock_queue.return_value.submit = AsyncMock()

            # Should raise the database error
            with pytest.raises(Exception, match="Database error"):
                await handle_import_organize(job)

        # Verify temp file was cleaned up
        assert not temp_file.exists()

        # Verify video status was updated to organize_failed
        mock_repository.update_video.assert_called()
        call_args = mock_repository.update_video.call_args
        assert call_args[0][0] == 1  # video_id
        assert call_args[1]["status"] == "organize_failed"

    async def test_multiple_videos_same_artist(self, mock_repository, mock_config, tmp_path):
        """Test organizing multiple videos for the same artist."""
        from fuzzbin.tasks.handlers import handle_import_organize

        parser = ArtistNFOParser()

        # Organize first video
        temp_file1 = tmp_path / "temp1" / "video1.mp4"
        temp_file1.parent.mkdir(parents=True, exist_ok=True)
        temp_file1.write_text("test video 1")

        job1 = Job(
            type=JobType.IMPORT_ORGANIZE,
            metadata={
                "video_id": 1,
                "temp_path": str(temp_file1),
            },
        )

        with (
            patch("fuzzbin.get_repository", return_value=mock_repository),
            patch("fuzzbin.get_config", return_value=mock_config),
            patch("fuzzbin.tasks.handlers.get_job_queue") as mock_queue,
        ):
            mock_queue.return_value.submit = AsyncMock()
            await handle_import_organize(job1)

        # Verify artist.nfo was created
        artist_nfo_path = mock_config.library_dir / "Nirvana" / "artist.nfo"
        assert artist_nfo_path.exists()
        _original_mtime = artist_nfo_path.stat().st_mtime

        # Organize second video for same artist
        temp_file2 = tmp_path / "temp2" / "video2.mp4"
        temp_file2.parent.mkdir(parents=True, exist_ok=True)
        temp_file2.write_text("test video 2")

        # Update mock to return different video but same artist
        mock_repository.get_video_by_id = AsyncMock(
            return_value={
                "id": 2,
                "title": "Come As You Are",
                "artist": "Nirvana",
                "album": "Nevermind",
                "year": 1991,
            }
        )

        job2 = Job(
            type=JobType.IMPORT_ORGANIZE,
            metadata={
                "video_id": 2,
                "temp_path": str(temp_file2),
            },
        )

        with (
            patch("fuzzbin.get_repository", return_value=mock_repository),
            patch("fuzzbin.get_config", return_value=mock_config),
            patch("fuzzbin.tasks.handlers.get_job_queue") as mock_queue,
        ):
            mock_queue.return_value.submit = AsyncMock()
            await handle_import_organize(job2)

        # Verify artist.nfo still exists and wasn't unnecessarily rewritten
        assert artist_nfo_path.exists()
        artist_nfo = parser.parse_file(artist_nfo_path)
        assert artist_nfo.name == "Nirvana"

        # Both videos should be in the artist directory
        video_files = list((mock_config.library_dir / "Nirvana").glob("*.mp4"))
        assert len(video_files) == 2
