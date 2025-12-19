"""Unit tests for NFO importer workflow."""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from fuzzbin.parsers.models import MusicVideoNFO
from fuzzbin.parsers.musicvideo_parser import MusicVideoNFOParser
from fuzzbin.workflows.nfo_importer import NFOImporter
from fuzzbin.workflows.spotify_importer import ImportResult


@pytest.fixture
def mock_repository():
    """Mock VideoRepository for testing."""
    repository = AsyncMock()
    repository.create_video = AsyncMock(return_value=1)
    repository.upsert_artist = AsyncMock(return_value=10)
    repository.link_video_artist = AsyncMock()
    repository.transaction = MagicMock()
    repository.transaction.__aenter__ = AsyncMock()
    repository.transaction.__aexit__ = AsyncMock()

    # Mock query for existence check
    query = AsyncMock()
    query.where_title = MagicMock(return_value=query)
    query.where_artist = MagicMock(return_value=query)
    query.execute = AsyncMock(return_value=[])
    repository.query = MagicMock(return_value=query)

    return repository


@pytest.fixture
def sample_nfo_directory(tmp_path):
    """Create directory with sample NFO files."""
    # Create musicvideo.nfo files
    musicvideo_nfo1 = tmp_path / "video1.nfo"
    musicvideo_nfo1.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<musicvideo>
    <title>Smells Like Teen Spirit</title>
    <artist>Nirvana</artist>
    <album>Nevermind</album>
    <year>1991</year>
    <director>Samuel Bayer</director>
    <genre>Rock</genre>
    <studio>DGC</studio>
</musicvideo>
""")

    musicvideo_nfo2 = tmp_path / "video2.nfo"
    musicvideo_nfo2.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<musicvideo>
    <title>Blurred Lines</title>
    <artist>Robin Thicke</artist>
    <album>Blurred Lines</album>
    <year>2013</year>
</musicvideo>
""")

    # Create artist.nfo file (should be filtered out)
    artist_nfo = tmp_path / "artist.nfo"
    artist_nfo.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<artist>
    <name>Nirvana</name>
</artist>
""")

    # Create malformed NFO file
    malformed_nfo = tmp_path / "malformed.nfo"
    malformed_nfo.write_text("This is not valid XML")

    # Create subdirectory with NFO
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    musicvideo_nfo3 = subdir / "video3.nfo"
    musicvideo_nfo3.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<musicvideo>
    <title>Closer</title>
    <artist>Nine Inch Nails</artist>
    <year>1994</year>
</musicvideo>
""")

    return tmp_path


@pytest.fixture
def nfo_importer(mock_repository):
    """Create NFOImporter instance for testing."""
    return NFOImporter(
        video_repository=mock_repository,
        initial_status="discovered",
        skip_existing=True,
    )


# File Discovery Tests


def test_discover_nfo_files_recursive(nfo_importer, sample_nfo_directory):
    """Test discovering NFO files recursively."""
    nfo_files = nfo_importer._discover_nfo_files(sample_nfo_directory, recursive=True)

    assert len(nfo_files) == 5  # 3 musicvideo + 1 artist + 1 malformed + 0 in subdir
    assert all(path.suffix == ".nfo" for path in nfo_files)


def test_discover_nfo_files_non_recursive(nfo_importer, sample_nfo_directory):
    """Test discovering NFO files without recursion."""
    nfo_files = nfo_importer._discover_nfo_files(sample_nfo_directory, recursive=False)

    # Should find 4 NFOs in root (not in subdir)
    assert len(nfo_files) == 4
    assert all(path.parent == sample_nfo_directory for path in nfo_files)


def test_discover_nfo_files_invalid_path(nfo_importer, tmp_path):
    """Test that invalid path raises ValueError."""
    invalid_path = tmp_path / "nonexistent"

    with pytest.raises(ValueError, match="Path does not exist"):
        nfo_importer._discover_nfo_files(invalid_path, recursive=True)


def test_discover_nfo_files_not_directory(nfo_importer, tmp_path):
    """Test that file path raises ValueError."""
    file_path = tmp_path / "file.txt"
    file_path.write_text("test")

    with pytest.raises(ValueError, match="not a directory"):
        nfo_importer._discover_nfo_files(file_path, recursive=True)


# NFO Type Identification Tests


def test_identify_musicvideo_nfo(nfo_importer, sample_nfo_directory):
    """Test identifying musicvideo.nfo files."""
    nfo_path = sample_nfo_directory / "video1.nfo"
    nfo_type = nfo_importer._identify_nfo_type(nfo_path)

    assert nfo_type == "musicvideo"


def test_identify_artist_nfo(nfo_importer, sample_nfo_directory):
    """Test identifying artist.nfo files."""
    nfo_path = sample_nfo_directory / "artist.nfo"
    nfo_type = nfo_importer._identify_nfo_type(nfo_path)

    assert nfo_type == "artist"


def test_identify_malformed_nfo(nfo_importer, sample_nfo_directory):
    """Test that malformed XML returns None."""
    nfo_path = sample_nfo_directory / "malformed.nfo"
    nfo_type = nfo_importer._identify_nfo_type(nfo_path)

    assert nfo_type is None


def test_identify_unrecognized_root(nfo_importer, tmp_path):
    """Test that unrecognized root element returns None."""
    nfo_path = tmp_path / "unknown.nfo"
    nfo_path.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<unknown>
    <data>test</data>
</unknown>
""")

    nfo_type = nfo_importer._identify_nfo_type(nfo_path)

    assert nfo_type is None


# NFO Filtering Tests


@pytest.mark.asyncio
async def test_filter_musicvideo_nfos(nfo_importer, sample_nfo_directory):
    """Test filtering to only musicvideo.nfo files."""
    nfo_files = nfo_importer._discover_nfo_files(sample_nfo_directory, recursive=True)
    musicvideo_nfos = await nfo_importer._filter_musicvideo_nfos(nfo_files)

    # Should have 3 musicvideo NFOs (2 in root + 1 in subdir)
    assert len(musicvideo_nfos) == 3

    # Verify each is a musicvideo type
    for nfo_path in musicvideo_nfos:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        assert root.tag == "musicvideo"


# Data Mapping Tests


def test_map_nfo_to_video_data_all_fields(nfo_importer):
    """Test mapping NFO with all fields to video data."""
    nfo = MusicVideoNFO(
        title="Smells Like Teen Spirit",
        artist="Nirvana",
        album="Nevermind",
        year=1991,
        director="Samuel Bayer",
        genre="Rock",
        studio="DGC",
    )

    video_data = nfo_importer._map_nfo_to_video_data(nfo)

    assert video_data["title"] == "Smells Like Teen Spirit"
    assert video_data["artist"] == "Nirvana"
    assert video_data["album"] == "Nevermind"
    assert video_data["year"] == 1991
    assert video_data["director"] == "Samuel Bayer"
    assert video_data["genre"] == "Rock"
    assert video_data["studio"] == "DGC"
    assert video_data["status"] == "discovered"
    assert video_data["download_source"] == "nfo_import"
    assert "nfo_file_path" not in video_data


def test_map_nfo_to_video_data_minimal(nfo_importer):
    """Test mapping NFO with only title and artist."""
    nfo = MusicVideoNFO(
        title="Test Title",
        artist="Test Artist",
    )

    video_data = nfo_importer._map_nfo_to_video_data(nfo)

    assert video_data["title"] == "Test Title"
    assert video_data["artist"] == "Test Artist"
    assert video_data["album"] is None
    assert video_data["year"] is None
    assert video_data["director"] is None
    assert video_data["genre"] is None
    assert video_data["studio"] is None


def test_map_nfo_to_video_data_with_file_path(nfo_importer, tmp_path):
    """Test mapping NFO with file path storage."""
    nfo = MusicVideoNFO(
        title="Test Title",
        artist="Test Artist",
    )
    nfo_path = tmp_path / "test.nfo"

    video_data = nfo_importer._map_nfo_to_video_data(nfo, nfo_file_path=nfo_path)

    assert "nfo_file_path" in video_data
    assert video_data["nfo_file_path"] == str(nfo_path.resolve())


# Validation Tests


def test_validate_critical_fields_valid(nfo_importer, tmp_path):
    """Test validation with valid title and artist."""
    nfo = MusicVideoNFO(
        title="Test Title",
        artist="Test Artist",
    )
    nfo_path = tmp_path / "test.nfo"

    result = nfo_importer._validate_critical_fields(nfo, nfo_path)

    assert result is True


def test_validate_critical_fields_missing_title(nfo_importer, tmp_path):
    """Test validation fails with missing title."""
    nfo = MusicVideoNFO(
        title=None,
        artist="Test Artist",
    )
    nfo_path = tmp_path / "test.nfo"

    result = nfo_importer._validate_critical_fields(nfo, nfo_path)

    assert result is False


def test_validate_critical_fields_missing_artist(nfo_importer, tmp_path):
    """Test validation fails with missing artist."""
    nfo = MusicVideoNFO(
        title="Test Title",
        artist=None,
    )
    nfo_path = tmp_path / "test.nfo"

    result = nfo_importer._validate_critical_fields(nfo, nfo_path)

    assert result is False


def test_validate_critical_fields_missing_both(nfo_importer, tmp_path):
    """Test validation fails with missing title and artist."""
    nfo = MusicVideoNFO(
        title=None,
        artist=None,
    )
    nfo_path = tmp_path / "test.nfo"

    result = nfo_importer._validate_critical_fields(nfo, nfo_path)

    assert result is False


# Existence Check Tests


@pytest.mark.asyncio
async def test_check_video_exists_found(nfo_importer, mock_repository):
    """Test existence check when video exists."""
    nfo = MusicVideoNFO(
        title="Test Title",
        artist="Test Artist",
    )

    # Mock query to return results
    mock_repository.query().execute = AsyncMock(return_value=[{"id": 1}])

    exists = await nfo_importer._check_video_exists(nfo)

    assert exists is True


@pytest.mark.asyncio
async def test_check_video_exists_not_found(nfo_importer, mock_repository):
    """Test existence check when video doesn't exist."""
    nfo = MusicVideoNFO(
        title="Test Title",
        artist="Test Artist",
    )

    # Mock query to return empty results
    mock_repository.query().execute = AsyncMock(return_value=[])

    exists = await nfo_importer._check_video_exists(nfo)

    assert exists is False


@pytest.mark.asyncio
async def test_check_video_exists_missing_fields(nfo_importer):
    """Test existence check with missing fields returns False."""
    nfo = MusicVideoNFO(
        title=None,
        artist=None,
    )

    exists = await nfo_importer._check_video_exists(nfo)

    assert exists is False


# Import Tests


@pytest.mark.asyncio
async def test_import_single_nfo_success(nfo_importer, mock_repository, tmp_path):
    """Test importing a single NFO file."""
    nfo = MusicVideoNFO(
        title="Test Title",
        artist="Test Artist",
        album="Test Album",
        year=2020,
    )
    nfo_path = tmp_path / "test.nfo"

    video_id = await nfo_importer._import_single_nfo(nfo, nfo_path)

    assert video_id == 1
    mock_repository.create_video.assert_called_once()
    mock_repository.upsert_artist.assert_called_once_with(name="Test Artist")
    mock_repository.link_video_artist.assert_called_once_with(
        video_id=1, artist_id=10, role="primary", position=0
    )


@pytest.mark.asyncio
async def test_import_single_nfo_with_featured_artists(nfo_importer, mock_repository, tmp_path):
    """Test importing NFO with featured artists."""
    nfo = MusicVideoNFO(
        title="Blurred Lines",
        artist="Robin Thicke",
        featured_artists=["T.I.", "Pharrell Williams"],
    )
    nfo_path = tmp_path / "test.nfo"

    # Mock upsert_artist to return different IDs
    mock_repository.upsert_artist = AsyncMock(side_effect=[10, 11, 12])

    video_id = await nfo_importer._import_single_nfo(nfo, nfo_path)

    assert video_id == 1
    assert mock_repository.upsert_artist.call_count == 3
    assert mock_repository.link_video_artist.call_count == 3

    # Verify featured artists were linked
    calls = mock_repository.link_video_artist.call_args_list
    assert calls[1][1]["role"] == "featured"
    assert calls[1][1]["position"] == 1
    assert calls[2][1]["role"] == "featured"
    assert calls[2][1]["position"] == 2


@pytest.mark.asyncio
async def test_import_from_directory_full_workflow(nfo_importer, mock_repository, sample_nfo_directory):
    """Test full workflow: import from directory."""
    result = await nfo_importer.import_from_directory(
        root_path=sample_nfo_directory,
        recursive=True,
        update_file_paths=True,
    )

    assert isinstance(result, ImportResult)
    assert result.total_tracks == 3  # 3 musicvideo NFOs
    assert result.imported_count == 3
    assert result.skipped_count == 0
    assert result.failed_count == 0


@pytest.mark.asyncio
async def test_import_skip_existing(nfo_importer, mock_repository, sample_nfo_directory):
    """Test skipping existing videos."""
    # Mock query to return existing video
    mock_repository.query().execute = AsyncMock(return_value=[{"id": 1}])

    result = await nfo_importer.import_from_directory(
        root_path=sample_nfo_directory,
        recursive=True,
        update_file_paths=False,
    )

    assert result.skipped_count == 3  # All 3 videos exist
    assert result.imported_count == 0


@pytest.mark.asyncio
async def test_import_with_missing_critical_fields(nfo_importer, mock_repository, tmp_path):
    """Test importing NFO with missing critical fields."""
    # Create NFO missing artist
    nfo_path = tmp_path / "invalid.nfo"
    nfo_path.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<musicvideo>
    <title>Test Title</title>
</musicvideo>
""")

    result = await nfo_importer.import_from_directory(
        root_path=tmp_path,
        recursive=False,
        update_file_paths=False,
    )

    assert result.failed_count == 1
    assert result.imported_count == 0
    assert len(result.failed_tracks) == 1
    assert "Missing critical fields" in result.failed_tracks[0]["error"]


@pytest.mark.asyncio
async def test_import_continues_on_error(nfo_importer, mock_repository, sample_nfo_directory):
    """Test that import continues when individual NFO fails."""
    # Make create_video fail for first call, succeed for rest
    mock_repository.create_video = AsyncMock(
        side_effect=[Exception("DB error"), 1, 2]
    )

    result = await nfo_importer.import_from_directory(
        root_path=sample_nfo_directory,
        recursive=True,
        update_file_paths=False,
    )

    assert result.failed_count == 1
    assert result.imported_count == 2
    assert len(result.failed_tracks) == 1


@pytest.mark.asyncio
async def test_import_invalid_directory(nfo_importer, tmp_path):
    """Test that importing from invalid directory raises ValueError."""
    invalid_path = tmp_path / "nonexistent"

    with pytest.raises(ValueError, match="Path does not exist"):
        await nfo_importer.import_from_directory(
            root_path=invalid_path,
            recursive=True,
            update_file_paths=False,
        )
