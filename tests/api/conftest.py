"""Shared pytest fixtures for API tests."""

import os
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
from fuzzbin.web.settings import APISettings, get_settings


# Test JWT secret used across all API tests
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


@pytest.fixture(autouse=True)
def set_jwt_secret_env(monkeypatch):
    """Set JWT secret environment variable for all API tests.
    
    This is required because APISettings now always requires jwt_secret,
    and create_app() calls get_settings() before dependency overrides are set.
    """
    monkeypatch.setenv("FUZZBIN_API_JWT_SECRET", TEST_JWT_SECRET)
    # Disable auth for general API tests (auth-specific tests override this)
    monkeypatch.setenv("FUZZBIN_API_AUTH_ENABLED", "false")
    monkeypatch.setenv("FUZZBIN_API_ALLOW_INSECURE_MODE", "true")
    # Clear the settings cache to pick up the new env vars
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def api_settings() -> APISettings:
    """Provide test API settings with auth disabled for general API tests."""
    return APISettings(
        host="127.0.0.1",
        port=8000,
        debug=True,
        allowed_origins=["*"],
        log_requests=False,  # Reduce noise in tests
        jwt_secret=TEST_JWT_SECRET,  # Required for auth
        auth_enabled=False,  # Disable auth for general API tests
        allow_insecure_mode=True,  # Required when auth is disabled
    )


@pytest.fixture
def test_database_config() -> DatabaseConfig:
    """Provide a test database configuration.
    
    Note: DatabaseConfig no longer has user-configurable fields.
    Tests should use direct VideoRepository instantiation with db_path.
    """
    return DatabaseConfig()


@pytest.fixture
def test_config(test_database_config: DatabaseConfig, tmp_path: Path) -> Config:
    """Provide a test configuration."""
    # Create library and config subdirectories for tests
    library_dir = tmp_path / "music_videos"
    config_dir = tmp_path / "config"
    library_dir.mkdir(exist_ok=True)
    config_dir.mkdir(exist_ok=True)
    
    return Config(
        config_dir=config_dir,
        library_dir=library_dir,
        database=test_database_config,
        logging=LoggingConfig(
            level="WARNING",  # Reduce noise in tests
            format="text",
            handlers=["console"],
        ),
    )


@pytest.fixture
def test_library_dir(test_config: Config) -> Path:
    """Get the library directory from the test config."""
    return test_config.library_dir


@pytest.fixture
def test_config_dir(test_config: Config) -> Path:
    """Get the config directory from the test config."""
    return test_config.config_dir


@pytest_asyncio.fixture
async def test_repository(tmp_path: Path) -> AsyncGenerator[VideoRepository, None]:
    """Provide a test database repository with migrations applied.
    
    Uses direct VideoRepository instantiation with temp database path.
    """
    from fuzzbin.core.db.migrator import Migrator
    
    db_path = tmp_path / "test_api.db"
    migrations_dir = Path(__file__).parent.parent.parent / "fuzzbin" / "core" / "db" / "migrations"
    
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
async def test_app(test_repository: VideoRepository, api_settings: APISettings, test_config: Config) -> AsyncGenerator[TestClient, None]:
    """
    Provide a FastAPI TestClient with test database and job queue.

    This fixture:
    1. Creates a fresh test database
    2. Overrides the repository dependency to use the test database
    3. Initializes job queue via app lifespan (auto-starts workers)
    4. Returns a TestClient for making HTTP requests
    5. Cleans up job queue on teardown
    """
    from fuzzbin.tasks import reset_job_queue

    # Override the global config before creating the app
    fuzzbin._config = test_config
    fuzzbin._repository = test_repository

    app = create_app()

    # Override the repository dependency
    async def override_get_repository() -> AsyncGenerator[VideoRepository, None]:
        yield test_repository

    app.dependency_overrides[get_repository] = override_get_repository

    # Create test client - lifespan hooks will run and start job queue
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    # Cleanup
    app.dependency_overrides.clear()
    # Reset job queue global state for next test
    reset_job_queue()


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


# ==================== File Management Test Fixtures ====================


@pytest_asyncio.fixture
async def video_with_file(
    test_app: TestClient, sample_video_data: dict, test_config: Config
) -> dict:
    """Create a video with an actual file on disk."""
    # Create video file inside the library directory
    media_dir = test_config.library_dir / "media"
    media_dir.mkdir(exist_ok=True)
    video_file = media_dir / "test_video.mp4"
    video_file.write_bytes(b"test video content for testing")

    # Create video record with file path
    video_data = sample_video_data.copy()
    video_data["video_file_path"] = str(video_file)

    response = test_app.post("/videos", json=video_data)
    assert response.status_code == 201
    
    result = response.json()
    return result


@pytest_asyncio.fixture
async def video_with_missing_file(
    test_app: TestClient, sample_video_data: dict, test_config: Config
) -> dict:
    """Create a video pointing to a non-existent file."""
    # Create video record with non-existent file path
    video_data = sample_video_data.copy()
    video_data["video_file_path"] = str(test_config.library_dir / "missing_video.mp4")

    response = test_app.post("/videos", json=video_data)
    assert response.status_code == 201

    return response.json()


@pytest.fixture
def orphan_file(test_config: Config) -> Path:
    """Create an orphaned video file not tracked in database."""
    orphan = test_config.library_dir / "orphan_video.mp4"
    orphan.write_bytes(b"orphan video content")
    return orphan
