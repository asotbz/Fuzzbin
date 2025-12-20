"""Shared pytest fixtures for API tests."""

from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

import fuzzbin
from fuzzbin.common.config import Config, DatabaseConfig, LoggingConfig
from fuzzbin.core.db import VideoRepository
from fuzzbin.web.main import create_app
from fuzzbin.web.dependencies import get_repository
from fuzzbin.web.settings import APISettings


@pytest.fixture
def api_settings() -> APISettings:
    """Provide test API settings."""
    return APISettings(
        host="127.0.0.1",
        port=8000,
        debug=True,
        allowed_origins=["*"],
        log_requests=False,  # Reduce noise in tests
    )


@pytest.fixture
def test_database_config(tmp_path: Path) -> DatabaseConfig:
    """Provide a test database configuration using temp directory."""
    db_path = tmp_path / "test_api.db"
    backup_dir = tmp_path / "backups"
    return DatabaseConfig(
        database_path=str(db_path),
        workspace_root=str(tmp_path),
        enable_wal_mode=False,  # Disable WAL in tests to avoid lock issues
        connection_timeout=30,
        backup_dir=str(backup_dir),
    )


@pytest.fixture
def test_config(test_database_config: DatabaseConfig) -> Config:
    """Provide a test configuration."""
    return Config(
        database=test_database_config,
        logging=LoggingConfig(
            level="WARNING",  # Reduce noise in tests
            format="text",
            handlers=["console"],
        ),
    )


@pytest_asyncio.fixture
async def test_repository(test_database_config: DatabaseConfig) -> AsyncGenerator[VideoRepository, None]:
    """Provide a test database repository with migrations applied."""
    repo = await VideoRepository.from_config(test_database_config)
    yield repo
    await repo.close()


@pytest_asyncio.fixture
async def test_app(test_repository: VideoRepository, api_settings: APISettings, test_config: Config) -> AsyncGenerator[TestClient, None]:
    """
    Provide a FastAPI TestClient with test database.

    This fixture:
    1. Creates a fresh test database
    2. Overrides the repository dependency to use the test database
    3. Returns a TestClient for making HTTP requests
    """
    # Override the global config before creating the app
    fuzzbin._config = test_config
    fuzzbin._repository = test_repository

    app = create_app()

    # Override the repository dependency
    async def override_get_repository() -> AsyncGenerator[VideoRepository, None]:
        yield test_repository

    app.dependency_overrides[get_repository] = override_get_repository

    # Create test client
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def sample_video_data() -> dict:
    """Provide sample video data for creating test videos."""
    return {
        "title": "Smells Like Teen Spirit",
        "artist": "Nirvana",
        "album": "Nevermind",
        "year": 1991,
        "director": "Samuel Bayer",
        "genre": "Grunge",
        "studio": "DGC Records",
    }


@pytest.fixture
def sample_video_data_2() -> dict:
    """Provide alternate sample video data."""
    return {
        "title": "Losing My Religion",
        "artist": "R.E.M.",
        "album": "Out of Time",
        "year": 1991,
        "director": "Tarsem Singh",
        "genre": "Alternative Rock",
    }


@pytest.fixture
def sample_video_data_3() -> dict:
    """Provide third sample video data."""
    return {
        "title": "Under the Bridge",
        "artist": "Red Hot Chili Peppers",
        "album": "Blood Sugar Sex Magik",
        "year": 1992,
        "director": "Gus Van Sant",
        "genre": "Alternative Rock",
    }


@pytest.fixture
def sample_artist_data() -> dict:
    """Provide sample artist data."""
    return {
        "name": "Nirvana",
        "biography": "American rock band formed in 1987",
        "image_url": "https://example.com/nirvana.jpg",
    }


@pytest.fixture
def sample_collection_data() -> dict:
    """Provide sample collection data."""
    return {
        "name": "90s Grunge Classics",
        "description": "The best grunge videos from the 1990s",
    }


@pytest.fixture
def sample_tag_data() -> dict:
    """Provide sample tag data."""
    return {
        "name": "grunge",
    }
