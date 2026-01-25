"""Shared pytest fixtures for all tests.

Important Pattern for API Client Tests:
---------------------------------------
When testing API clients that support environment variable overrides (e.g., DISCOGS_API_KEY,
IMVDB_APP_KEY), tests must clear these env vars to prevent real credentials from interfering
with mock credentials. Use an autouse fixture in your test file:

    @pytest.fixture(autouse=True)
    def clear_api_env_vars(monkeypatch):
        \"\"\"Clear API environment variables before each test.\"\"\"
        monkeypatch.delenv("YOUR_API_KEY", raising=False)
        monkeypatch.delenv("YOUR_API_SECRET", raising=False)

See tests/unit/test_discogs_client.py and tests/unit/test_imvdb_client.py for examples.
"""

import pytest
import pytest_asyncio
import httpx
import respx
from pathlib import Path

from fuzzbin.common.config import Config, HTTPConfig, LoggingConfig, DatabaseConfig
from fuzzbin.core.db import VideoRepository, DatabaseBackup


@pytest.fixture
def sample_config() -> Config:
    """Provide a sample configuration for tests."""
    return Config(
        http=HTTPConfig(
            timeout=30,
            max_redirects=5,
            verify_ssl=True,
        ),
        logging=LoggingConfig(
            level="DEBUG",
            format="text",
            handlers=["console"],
        ),
    )


@pytest.fixture
def http_config() -> HTTPConfig:
    """Provide a sample HTTP configuration for tests."""
    return HTTPConfig(
        timeout=10,
        max_redirects=3,
        verify_ssl=True,
    )


@pytest_asyncio.fixture
async def async_httpx_client() -> httpx.AsyncClient:
    """Provide an async httpx client for tests."""
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def mock_http():
    """Provide a respx mock for httpx requests."""
    with respx.mock:
        yield respx


@pytest.fixture
def database_config() -> DatabaseConfig:
    """Provide a test database configuration.

    Note: DatabaseConfig no longer has user-configurable fields.
    Tests should use direct VideoRepository instantiation with db_path.
    """
    return DatabaseConfig()


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Provide a test config directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def library_dir(tmp_path: Path) -> Path:
    """Provide a test library directory."""
    library_dir = tmp_path / "music_videos"
    library_dir.mkdir(parents=True, exist_ok=True)
    return library_dir


@pytest_asyncio.fixture
async def test_db(config_dir: Path) -> VideoRepository:
    """Provide a test database with migrations applied.

    Uses direct VideoRepository instantiation with temp database path.
    """
    from fuzzbin.core.db.migrator import Migrator

    db_path = config_dir / "test_fuzzbin.db"
    migrations_dir = Path(__file__).parent.parent / "fuzzbin" / "core" / "db" / "migrations"

    repo = VideoRepository(
        db_path=db_path,
        enable_wal=False,  # Disable WAL mode in tests to avoid lock issues
        timeout=30,
    )
    await repo.connect()

    # Run migrations
    migrator = Migrator(db_path, migrations_dir, enable_wal=False)
    await migrator.run_migrations(connection=repo._connection)

    yield repo
    await repo.close()


@pytest_asyncio.fixture
async def test_repository(test_db: VideoRepository) -> VideoRepository:
    """Provide a ready-to-use test repository."""
    return test_db


@pytest.fixture
def sample_video_metadata() -> dict:
    """Provide sample video metadata for testing."""
    return {
        "title": "Smells Like Teen Spirit",
        "artist": "Nirvana",
        "album": "Nevermind",
        "year": 1991,
        "director": "Samuel Bayer",
        "genre": "Grunge",
        "studio": "DGC Records",
        "imvdb_video_id": "12345",
        "youtube_id": "hTWKbfoikeg",
    }


@pytest.fixture
def sample_artist_metadata() -> dict:
    """Provide sample artist metadata for testing."""
    return {
        "name": "Nirvana",
        "imvdb_entity_id": "67890",
        "discogs_artist_id": 12345,
        "biography": "American rock band formed in 1987",
        "image_url": "https://example.com/nirvana.jpg",
    }


@pytest_asyncio.fixture
async def backup_manager(tmp_path: Path) -> DatabaseBackup:
    """Provide a DatabaseBackup instance for testing."""
    return DatabaseBackup()
