"""Shared pytest fixtures for all tests."""

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
def database_config(tmp_path: Path) -> DatabaseConfig:
    """Provide a test database configuration."""
    db_path = tmp_path / "test_fuzzbin.db"
    backup_dir = tmp_path / "backups"
    return DatabaseConfig(
        database_path=str(db_path),
        workspace_root=str(tmp_path),
        enable_wal_mode=False,  # Disable WAL mode in tests to avoid lock issues
        connection_timeout=30,
        backup_dir=str(backup_dir),
    )


@pytest_asyncio.fixture
async def test_db(database_config: DatabaseConfig) -> VideoRepository:
    """Provide a test database with migrations applied."""
    repo = await VideoRepository.from_config(database_config)
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
