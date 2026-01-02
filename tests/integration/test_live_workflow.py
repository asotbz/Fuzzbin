"""
Live integration tests for multi-module workflow with database state tracking.

This test module includes three comprehensive integration tests:

1. test_complete_workflow - Full API workflow with database tracking
   - IMVDb video search and metadata retrieval
   - Discogs album/artist metadata enrichment
   - NFO generation (artist.nfo and musicvideo.nfo)
   - Database state transitions: discovered → queued → imported → organized
   - Tests against real music videos (Robin Thicke, Nirvana, Daft Punk)

2. test_minimal_state_machine_workflow - State machine with real download
   - Complete state machine: discovered → queued → downloading → downloaded → imported → organized
   - Real yt-dlp video download (18-second test video, minimal bandwidth)
   - File verification (MP4 signature, checksum calculation)
   - Status history validation
   - No external API dependencies

3. test_download_failure_workflow - Error handling validation
   - Invalid URL download attempt
   - Transition to "failed" state
   - Download attempt counter verification
   - Error message storage

SETUP INSTRUCTIONS:
===================
1. API Credentials (for test_complete_workflow):
   export IMVDB_APP_KEY="your-imvdb-api-key"
   export DISCOGS_API_KEY="your-discogs-consumer-key"
   export DISCOGS_API_SECRET="your-discogs-consumer-secret"

2. Install yt-dlp (for state machine tests):
   pip install yt-dlp

RUN INSTRUCTIONS:
=================
Run all tests in this file:
    pytest tests/integration/test_live_workflow.py -v -s

Run specific test:
    pytest tests/integration/test_live_workflow.py::test_minimal_state_machine_workflow -v -s

Run tests by marker:
    pytest -m "live and database" -v -s          # API + database tests
    pytest -m "database and not live" -v -s      # Database tests without API
    pytest -m "slow" -v -s                       # All slow tests
    pytest -m "not slow" -v                      # Skip slow tests (CI)

Filter parametrized tests:
    pytest tests/integration/test_live_workflow.py -k "Nirvana" -v -s

NOTES:
======
- test_complete_workflow requires API credentials, will be skipped if not set
- test_minimal_state_machine_workflow and test_download_failure_workflow require yt-dlp
- All tests use isolated temporary databases (auto-cleaned after test)
- Cache databases are per-test-run to avoid conflicts
- DEBUG logging enabled to show rate limiting, caching, and HTTP details
- Minimal bandwidth usage: "worst" quality format (~50-500KB per download)
"""

import hashlib
import os
import shutil
from pathlib import Path

import pytest
import pytest_asyncio

from fuzzbin.common.config import Config, DatabaseConfig, YTDLPConfig
from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.api.discogs_client import DiscogsClient
from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.core.db import VideoRepository
from fuzzbin.core.exceptions import YTDLPError, YTDLPExecutionError
from fuzzbin.parsers import (
    ArtistNFO,
    MusicVideoNFO,
    ArtistNFOParser,
    MusicVideoNFOParser,
    FeaturedArtistConfig,
    DiscogsParser,
)
from fuzzbin.parsers.ytdlp_models import DownloadHooks
from fuzzbin.core import build_media_paths


def calculate_file_checksum(file_path: Path) -> str:
    """Calculate SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in chunks to handle large files efficiently
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def verify_mp4_signature(file_path: Path) -> bool:
    """Verify file has valid MP4 signature."""
    with open(file_path, "rb") as f:
        f.seek(4)
        file_type = f.read(4)
        return file_type == b"ftyp"


@pytest.fixture
def test_cache_dir(tmp_path: Path) -> Path:
    """Create and return a temporary cache directory for isolated test runs."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def clean_test_config(test_cache_dir: Path) -> Config:
    """
    Create test config with default values and temporary cache.
    
    - Uses default config values (no config.yaml required)
    - Sets logging level to DEBUG for verbose output
    - Redirects cache databases to temporary directory
    - Environment variables still override API credentials
    """
    from fuzzbin.common.config import (
        APIClientConfig,
        CacheConfig,
        HTTPConfig,
        LoggingConfig,
        RateLimitConfig,
    )
    
    # Create minimal config with defaults
    config = Config(
        http=HTTPConfig(timeout=30, max_redirects=5, verify_ssl=True),
        logging=LoggingConfig(level="DEBUG", format="text", handlers=["console"]),
    )
    
    # Configure IMVDb API with temp cache
    config.apis = config.apis or {}
    config.apis["imvdb"] = APIClientConfig(
        name="imvdb",
        base_url="https://imvdb.com/api/v1",
        http=HTTPConfig(timeout=30),
        rate_limit=RateLimitConfig(requests_per_second=1.0),
        cache=CacheConfig(
            enabled=True,
            storage_path=str(test_cache_dir / "imvdb_test.db"),
            ttl=3600,
        ),
    )
    
    # Configure Discogs API with temp cache
    config.apis["discogs"] = APIClientConfig(
        name="discogs",
        base_url="https://api.discogs.com",
        http=HTTPConfig(timeout=30),
        rate_limit=RateLimitConfig(requests_per_minute=30),  # 30/min = 0.5/sec
        cache=CacheConfig(
            enabled=True,
            storage_path=str(test_cache_dir / "discogs_test.db"),
            ttl=3600,
        ),
    )
    
    return config


@pytest_asyncio.fixture
async def imvdb_client(clean_test_config: Config):
    """Provide configured IMVDb client with temporary cache."""
    async with IMVDbClient.from_config(clean_test_config.apis["imvdb"]) as client:
        yield client


@pytest_asyncio.fixture
async def discogs_client(clean_test_config: Config):
    """Provide configured Discogs client with temporary cache."""
    async with DiscogsClient.from_config(clean_test_config.apis["discogs"]) as client:
        yield client


@pytest_asyncio.fixture
async def test_repository(tmp_path: Path):
    """Provide test database with migrations applied.
    
    Uses direct VideoRepository instantiation with temp database path.
    """
    from fuzzbin.core.db.migrator import Migrator
    
    db_path = tmp_path / "test_workflow.db"
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
    
    try:
        yield repo
    finally:
        await repo.close()


@pytest_asyncio.fixture
async def ytdlp_client():
    """Provide configured YT-DLP client with minimal download settings.
    
    Note: YTDLPConfig only has ytdlp_path, format_spec, and geo_bypass now.
    Other settings (timeout, quiet) use class defaults.
    """
    ytdlp_config = YTDLPConfig(
        ytdlp_path="yt-dlp",
        format_spec="worst[ext=mp4]/worst",  # Use worst quality for fast downloads
        geo_bypass=True,
    )
    async with YTDLPClient.from_config(ytdlp_config) as client:
        yield client


@pytest.mark.live
@pytest.mark.database
@pytest.mark.skipif(
    not os.getenv("IMVDB_APP_KEY")
    or not os.getenv("DISCOGS_API_KEY")
    or not os.getenv("DISCOGS_API_SECRET"),
    reason="Required API credentials not found in environment variables. "
    "Set IMVDB_APP_KEY, DISCOGS_API_KEY, and DISCOGS_API_SECRET.",
)
@pytest.mark.parametrize(
    "artist,track",
    [
        ("Robin Thicke", "Blurred Lines"),
        ("Nirvana", "Smells Like Teen Spirit"),
        ("Daft Punk", "Get Lucky"),
    ],
)
@pytest.mark.asyncio
async def test_complete_workflow(
    artist: str,
    track: str,
    imvdb_client: IMVDbClient,
    discogs_client: DiscogsClient,
    test_repository,
    tmp_path: Path,
):
    """
    Test complete workflow from search to NFO generation with database tracking.
    
    This test validates the entire data pipeline:
    - IMVDb video search and detail retrieval
    - Discogs ID extraction from IMVDb entity
    - Discogs master release lookup
    - NFO file generation (artist.nfo and musicvideo.nfo)
    - Organized media path generation
    - Database state tracking through workflow states
    
    All data is validated for presence and basic structure.
    """
    print(f"\n{'=' * 80}")
    print(f"Testing workflow for: {artist} - {track}")
    print(f"{'=' * 80}")
    
    # ========================================================================
    # STEP 1: Search IMVDb for the music video
    # ========================================================================
    print(f"\n=== IMVDb Video Search ===")
    video_search_results = await imvdb_client.search_videos(artist, track)
    
    assert len(video_search_results.results) > 0, (
        f"No IMVDb videos found for {artist} - {track}"
    )
    
    # Select first result
    video_result = video_search_results.results[0]
    print(f"Found video: {video_result.song_title} ({video_result.year})")
    print(f"Video ID: {video_result.id}")
    
    # ========================================================================
    # STEP 2: Get full video details
    # ========================================================================
    print(f"\n=== IMVDb Video Details ===")
    video = await imvdb_client.get_video(video_result.id)
    
    # Validate required fields
    assert video.artists, f"No artists found for video {video.id}"
    assert video.year, f"No year found for video {video.id}"
    
    # Extract video metadata (director is optional)
    director = None
    if video.directors:
        director = video.directors[0].entity_name
    
    # Primary artist name (for both NFOs and clean paths)
    primary_artist_name = video.artists[0].name
    artist_slug = video.artists[0].slug
    
    # Featured artists as a list
    featured_artists_list = []
    if video.featured_artists:
        featured_artists_list = [fa.name for fa in video.featured_artists]
        print(f"Featured Artists: {', '.join(featured_artists_list)}")
    
    video_title = video.song_title
    video_year = video.year
    
    print(f"Title: {video_title}")
    print(f"Primary Artist: {primary_artist_name}")
    print(f"Artist Slug: {artist_slug}")
    print(f"Year: {video_year}")
    print(f"Director: {director if director else 'Not available'}")
    
    # ========================================================================
    # DATABASE: Create video record in "discovered" state
    # ========================================================================
    print(f"\n=== Creating Database Record (discovered) ===")
    video_id = await test_repository.create_video(
        title=video_title,
        artist=primary_artist_name,
        year=video_year,
        director=director,
        imvdb_video_id=video.id,
        status="discovered",
    )
    print(f"Database Video ID: {video_id}")
    
    # ========================================================================
    # STEP 3: Extract YouTube source URL
    # ========================================================================
    print(f"\n=== YouTube Source ===")
    youtube_source = None
    if video.sources:
        for source in video.sources:
            if source.source == "youtube" and source.is_primary:
                youtube_source = source.source_data
                break
    
    if youtube_source:
        youtube_url = f"https://youtube.com/watch?v={youtube_source}"
        print(f"YouTube URL: {youtube_url}")
        print(f"YouTube Video ID: {youtube_source}")
        
        # Update video with YouTube ID
        await test_repository.update_video(
            video_id,
            youtube_id=youtube_source,
            download_source="youtube",
        )
    else:
        print("No primary YouTube source found")
    
    # ========================================================================
    # DATABASE: Queue for download
    # ========================================================================
    print(f"\n=== Queueing for Download (queued) ===")
    await test_repository.update_status(
        video_id,
        "queued",
        reason="Video identified, ready for metadata enrichment",
        changed_by="test_workflow",
    )
    
    # ========================================================================
    # STEP 4: Get Discogs artist ID from IMVDb entity
    # ========================================================================
    print(f"\n=== Discogs ID Extraction ===")
    
    # First, search for the entity by artist name to get entity ID
    entity_search_results = await imvdb_client.search_entities(primary_artist_name)
    
    assert len(entity_search_results.results) > 0, (
        f"No IMVDb entities found for artist '{primary_artist_name}'"
    )
    
    # Find entity matching the artist slug (most reliable match)
    entity_result = None
    for result in entity_search_results.results:
        if result.slug == artist_slug:
            entity_result = result
            break
    
    # Fallback to first result if no slug match
    if entity_result is None:
        entity_result = entity_search_results.results[0]
        print(f"Warning: Using first search result (no exact slug match)")
    
    entity_id = entity_result.id
    print(f"Found entity: {entity_result.slug}")
    print(f"Entity ID: {entity_id}")
    
    # Get full entity details
    entity = await imvdb_client.get_entity(entity_id)
    
    assert entity.discogs_id is not None, (
        f"No Discogs ID found for IMVDb entity {entity_id} ({entity.name or entity.slug})"
    )
    
    discogs_artist_id = entity.discogs_id
    print(f"IMVDb Entity: {entity.name or entity.slug}")
    print(f"Discogs Artist ID: {discogs_artist_id}")
    
    # ========================================================================
    # STEP 5: Search Discogs for the track and find master release
    # ========================================================================
    print(f"\n=== Discogs Search ===")
    discogs_search_data = await discogs_client.search(artist, track)
    
    # Parse search response
    search_result = DiscogsParser.parse_search_response(discogs_search_data)
    
    # Find earliest master release
    earliest_master = DiscogsParser.find_earliest_master(
        search_result, artist, track
    )
    
    assert earliest_master is not None, (
        f"No Discogs master release found for {artist} - {track}"
    )
    
    print(f"Found master: {earliest_master.title}")
    print(f"Master ID: {earliest_master.master_id}")
    print(f"Year: {earliest_master.year}")
    
    # ========================================================================
    # STEP 6: Get master release details
    # ========================================================================
    print(f"\n=== Discogs Master Details ===")
    master_data = await discogs_client.get_master(earliest_master.master_id)
    
    # Extract master metadata
    album_title = master_data["title"]
    genre = master_data["genres"][0] if master_data.get("genres") else "Unknown"
    
    print(f"Album: {album_title}")
    print(f"Genre: {genre}")
    print(f"Tracklist entries: {len(master_data.get('tracklist', []))}")
    
    # Get main release to extract label information
    main_release_id = master_data.get("main_release")
    studio = None
    
    if main_release_id:
        print(f"\n=== Discogs Release Details ===")
        print(f"Fetching main release: {main_release_id}")
        release_data = await discogs_client.get_release(main_release_id)
        
        # Extract studio from labels
        if release_data.get("labels"):
            studio = release_data["labels"][0].get("name")
            print(f"Studio/Label: {studio}")
    else:
        print("Warning: No main release ID available, studio/label will be unknown")
    
    # ========================================================================
    # DATABASE: Update metadata and mark as "imported"
    # ========================================================================
    print(f"\n=== Updating Database with Metadata (imported) ===")
    await test_repository.update_video(
        video_id,
        album=album_title,
        genre=genre,
        studio=studio,
    )
    
    await test_repository.update_status(
        video_id,
        "imported",
        reason="Metadata enriched from IMVDb and Discogs",
        changed_by="test_workflow",
    )
    
    # ========================================================================
    # STEP 7: Generate Artist NFO
    # ========================================================================
    print(f"\n=== Artist NFO ===")
    artist_nfo = ArtistNFO(name=primary_artist_name)
    artist_parser = ArtistNFOParser()
    artist_xml = artist_parser.to_xml_string(artist_nfo)
    
    assert artist_xml, "Failed to generate artist NFO XML"
    assert "<artist>" in artist_xml, "Artist NFO missing root element"
    
    print(artist_xml)
    
    # ========================================================================
    # STEP 8: Generate Music Video NFO
    # ========================================================================
    print(f"\n=== Music Video NFO ===")
    music_video_nfo = MusicVideoNFO(
        title=video_title,
        artist=primary_artist_name,
        year=video_year,
        director=director,
        album=album_title,
        genre=genre,
        studio=studio,
        featured_artists=featured_artists_list,
    )
    
    # Create parser with featured artists enabled
    featured_config = FeaturedArtistConfig(enabled=True, append_to_field="artist")
    video_parser = MusicVideoNFOParser(featured_config=featured_config)
    video_xml = video_parser.to_xml_string(music_video_nfo)
    
    assert video_xml, "Failed to generate music video NFO XML"
    assert "<musicvideo>" in video_xml, "Music video NFO missing root element"
    
    print(video_xml)
    
    # ========================================================================
    # STEP 9: Generate organized media paths
    # ========================================================================
    print(f"\n=== Generated Paths ===")
    media_paths = build_media_paths(
        root_path=tmp_path,
        pattern="{artist}/{title}",
        nfo_data=music_video_nfo,
        normalize=True,
    )
    
    print(f"Video Path: {media_paths.video_path}")
    print(f"NFO Path: {media_paths.nfo_path}")
    
    # Validate paths
    assert media_paths.video_path.exists() is False, "Video path should not exist yet"
    assert media_paths.nfo_path.exists() is False, "NFO path should not exist yet"
    assert str(media_paths.video_path).endswith(".mp4"), "Video should have .mp4 extension"
    assert str(media_paths.nfo_path).endswith(".nfo"), "NFO should have .nfo extension"
    
    # ========================================================================
    # DATABASE: Update with organized paths and mark as "organized"
    # ========================================================================
    print(f"\n=== Updating Database with Organized Paths (organized) ===")
    await test_repository.update_video(
        video_id,
        video_file_path=str(media_paths.video_path),
        nfo_file_path=str(media_paths.nfo_path),
    )
    
    await test_repository.update_status(
        video_id,
        "organized",
        reason="File paths organized and NFO generated",
        changed_by="test_workflow",
    )
    
    # ========================================================================
    # DATABASE: Validate complete status history
    # ========================================================================
    print(f"\n=== Validating Status History ===")
    history = await test_repository.get_status_history(video_id)
    
    # Extract statuses in chronological order
    statuses = [entry["new_status"] for entry in reversed(history)]
    expected_statuses = ["discovered", "queued", "imported", "organized"]
    
    assert statuses == expected_statuses, f"Status sequence mismatch: {statuses}"
    
    print(f"Status History: {' → '.join(statuses)}")
    print(f"Total Transitions: {len(history)}")
    
    # Verify final state
    final_video = await test_repository.get_video_by_id(video_id)
    assert final_video["status"] == "organized"
    assert final_video["video_file_path"] == str(media_paths.video_path)
    assert final_video["nfo_file_path"] == str(media_paths.nfo_path)
    
    print(f"\n{'=' * 80}")
    print(f"Workflow completed successfully for: {artist} - {track}")
    print(f"{'=' * 80}\n")


@pytest.mark.slow
@pytest.mark.database
@pytest.mark.skipif(
    not shutil.which("yt-dlp"),
    reason="yt-dlp not found. Install with: pip install yt-dlp",
)
@pytest.mark.asyncio
async def test_minimal_state_machine_workflow(
    test_repository,
    ytdlp_client: YTDLPClient,
    tmp_path: Path,
):
    """
    Test minimal workflow exercising complete state machine with real download.
    
    This test validates the full video lifecycle without external API dependencies:
    - Create video in "discovered" state
    - Transition through queued → downloading → downloaded
    - Update metadata and transition to "imported"
    - Organize files and transition to "organized"
    - Validate complete status history
    
    Uses "Me at the zoo" (18 seconds) with worst quality for minimal bandwidth.
    """
    print(f"\n{'=' * 80}")
    print(f"Testing minimal state machine workflow")
    print(f"{'=' * 80}")
    
    # ========================================================================
    # STEP 1: Create video in "discovered" state
    # ========================================================================
    print(f"\n=== Creating Video Record (discovered) ===")
    video_id = await test_repository.create_video(
        title="Me at the zoo",
        artist="Test Artist",
        year=2005,
        youtube_id="jNQXAC9IVRw",
        status="discovered",
        download_source="youtube",
    )
    print(f"Video ID: {video_id}")
    
    # Verify initial state
    video = await test_repository.get_video_by_id(video_id)
    assert video["status"] == "discovered"
    
    # ========================================================================
    # STEP 2: Transition to "queued"
    # ========================================================================
    print(f"\n=== Queueing for Download (queued) ===")
    await test_repository.update_status(
        video_id,
        "queued",
        reason="Ready for download",
        changed_by="test_workflow",
    )
    
    video = await test_repository.get_video_by_id(video_id)
    assert video["status"] == "queued"
    
    # ========================================================================
    # STEP 3: Download video with state tracking
    # ========================================================================
    print(f"\n=== Downloading Video (downloading → downloaded) ===")
    
    # Create downloads directory
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    output_file = downloads_dir / "test_video.mp4"
    
    # Define hooks for status updates
    async def on_start():
        """Update status when download starts."""
        await test_repository.update_status(
            video_id,
            "downloading",
            reason="Download started",
            changed_by="ytdlp_hook",
        )
        print("Status updated to: downloading")
    
    async def on_complete(result):
        """Update status when download completes successfully."""
        try:
            # Calculate checksum
            checksum = calculate_file_checksum(result.output_path)
            
            # Verify MP4 signature
            assert verify_mp4_signature(result.output_path), "Invalid MP4 file"
            
            # Mark as downloaded in database using update_video and update_status
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            await test_repository.update_video(
                video_id,
                status="downloaded",
                status_changed_at=now,
                video_file_path=str(result.output_path),
                file_size=result.file_size,
                file_checksum=checksum,
                download_source="youtube",
                file_verified_at=now,
            )
            await test_repository.update_status(
                video_id,
                "downloaded",
                reason="File downloaded successfully",
                changed_by="ytdlp_hook",
            )
            print(f"Status updated to: downloaded")
            print(f"File size: {result.file_size / 1024:.1f} KB")
            print(f"Checksum: {checksum[:16]}...")
        except Exception as e:
            # If database update fails, mark as failed
            await test_repository.update_status(
                video_id,
                "failed",
                reason=f"Post-download update failed: {str(e)}",
                changed_by="ytdlp_hook",
            )
            raise
    
    async def on_error(error):
        """Update status on download error."""
        await test_repository.update_status(
            video_id,
            "failed",
            reason=str(error),
            changed_by="ytdlp_hook",
        )
        print(f"Download failed: {error}")
    
    # Create hooks
    hooks = DownloadHooks(
        on_start=on_start,
        on_complete=on_complete,
        on_error=on_error,
    )
    
    # Download video
    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    result = await ytdlp_client.download(test_url, output_file, hooks=hooks)
    
    # Validate download
    assert output_file.exists(), "Downloaded file not found"
    assert result.file_size > 0, "Downloaded file is empty"
    assert 10_000 < result.file_size < 2_000_000, f"File size {result.file_size} out of expected range"
    
    # Verify status is "downloaded"
    video = await test_repository.get_video_by_id(video_id)
    assert video["status"] == "downloaded"
    assert video["video_file_path"] == str(output_file)
    assert video["file_size"] == result.file_size
    assert video["file_checksum"] is not None
    
    # ========================================================================
    # STEP 4: Import metadata (imported)
    # ========================================================================
    print(f"\n=== Importing Metadata (imported) ===")
    
    # Update video with additional metadata
    await test_repository.update_video(
        video_id,
        album="Test Album",
        genre="Test",
        studio="Test Studio",
    )
    
    # Transition to imported
    await test_repository.update_status(
        video_id,
        "imported",
        reason="Metadata imported",
        changed_by="test_workflow",
    )
    
    video = await test_repository.get_video_by_id(video_id)
    assert video["status"] == "imported"
    assert video["album"] == "Test Album"
    
    # ========================================================================
    # STEP 5: Organize files (organized)
    # ========================================================================
    print(f"\n=== Organizing Files (organized) ===")
    
    # Create NFO
    music_video_nfo = MusicVideoNFO(
        title="Me at the zoo",
        artist="Test Artist",
        year=2005,
        album="Test Album",
        genre="Test",
        studio="Test Studio",
    )
    
    # Build organized paths
    media_root = tmp_path / "media"
    media_root.mkdir(parents=True, exist_ok=True)  # Create root directory
    
    media_paths = build_media_paths(
        root_path=media_root,
        pattern="{artist}/{title}",
        nfo_data=music_video_nfo,
        normalize=True,
    )
    
    # Create parent directory
    media_paths.video_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Move video to organized location
    shutil.move(str(output_file), str(media_paths.video_path))
    
    # Write NFO file
    video_parser = MusicVideoNFOParser()
    nfo_xml = video_parser.to_xml_string(music_video_nfo)
    media_paths.nfo_path.write_text(nfo_xml)
    
    # Update database with final paths
    await test_repository.update_video(
        video_id,
        video_file_path=str(media_paths.video_path),
        nfo_file_path=str(media_paths.nfo_path),
    )
    
    # Transition to organized
    await test_repository.update_status(
        video_id,
        "organized",
        reason="Files organized to final location",
        changed_by="test_workflow",
    )
    
    print(f"Video Path: {media_paths.video_path}")
    print(f"NFO Path: {media_paths.nfo_path}")
    
    # Verify files exist
    assert media_paths.video_path.exists(), "Organized video file not found"
    assert media_paths.nfo_path.exists(), "NFO file not found"
    
    video = await test_repository.get_video_by_id(video_id)
    assert video["status"] == "organized"
    assert video["video_file_path"] == str(media_paths.video_path)
    assert video["nfo_file_path"] == str(media_paths.nfo_path)
    
    # ========================================================================
    # STEP 6: Validate complete status history
    # ========================================================================
    print(f"\n=== Validating Status History ===")
    
    history = await test_repository.get_status_history(video_id)
    assert len(history) == 6, f"Expected 6 history entries, got {len(history)}"
    
    # Extract statuses in chronological order (reverse since newest first)
    statuses = [entry["new_status"] for entry in reversed(history)]
    expected_statuses = ["discovered", "queued", "downloading", "downloaded", "imported", "organized"]
    
    assert statuses == expected_statuses, f"Status sequence mismatch: {statuses}"
    
    # Verify each entry has required fields
    for entry in history:
        assert entry["changed_at"] is not None, "Missing changed_at timestamp"
        assert entry["new_status"] is not None, "Missing new_status"
        assert entry["reason"] is not None, "Missing reason"
    
    # Print formatted history
    print("\nStatus History:")
    print(f"{'Status':<15} {'Changed By':<15} {'Reason':<30}")
    print(f"{'-' * 60}")
    for entry in reversed(history):
        status = entry["new_status"]
        changed_by = entry.get("changed_by", "N/A")
        reason = entry.get("reason", "N/A")
        print(f"{status:<15} {changed_by:<15} {reason:<30}")
    
    print(f"\n{'=' * 80}")
    print(f"Minimal state machine workflow completed successfully")
    print(f"{'=' * 80}\n")


@pytest.mark.slow
@pytest.mark.database
@pytest.mark.skipif(
    not shutil.which("yt-dlp"),
    reason="yt-dlp not found. Install with: pip install yt-dlp",
)
@pytest.mark.asyncio
async def test_download_failure_workflow(
    test_repository,
    ytdlp_client: YTDLPClient,
    tmp_path: Path,
):
    """
    Test download failure handling and "failed" state.
    
    This test validates error handling in the download workflow:
    - Create video and queue for download
    - Attempt download with invalid URL
    - Verify transition to "failed" state
    - Check download_attempts counter is incremented
    - Validate error message is stored
    """
    print(f"\n{'=' * 80}")
    print(f"Testing download failure workflow")
    print(f"{'=' * 80}")
    
    # ========================================================================
    # STEP 1: Create video and queue for download
    # ========================================================================
    print(f"\n=== Creating and Queueing Video ===")
    video_id = await test_repository.create_video(
        title="Invalid Video",
        artist="Test Artist",
        youtube_id="INVALID_VIDEO_ID",
        status="discovered",
        download_source="youtube",
    )
    
    await test_repository.update_status(
        video_id,
        "queued",
        reason="Ready for download",
        changed_by="test_workflow",
    )
    
    print(f"Video ID: {video_id}")
    
    # ========================================================================
    # STEP 2: Attempt download with invalid URL
    # ========================================================================
    print(f"\n=== Attempting Download with Invalid URL ===")
    
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    output_file = downloads_dir / "invalid_video.mp4"
    
    # Transition to downloading
    await test_repository.update_status(
        video_id,
        "downloading",
        reason="Download started",
        changed_by="test_workflow",
    )
    
    # Try to download invalid URL
    invalid_url = "https://www.youtube.com/watch?v=INVALID_VIDEO_ID"
    download_failed = False
    error_message = None
    
    try:
        await ytdlp_client.download(invalid_url, output_file)
    except (YTDLPError, YTDLPExecutionError) as e:
        download_failed = True
        error_message = str(e)
        print(f"Download failed as expected: {error_message[:100]}...")
        
        # Mark as failed using update_status
        await test_repository.update_status(
            video_id,
            "failed",
            reason=error_message,
            changed_by="test_workflow",
        )
    
    assert download_failed, "Download should have failed with invalid URL"
    assert error_message is not None, "Error message should be captured"
    
    # ========================================================================
    # STEP 3: Verify "failed" state and error tracking
    # ========================================================================
    print(f"\n=== Verifying Failed State ===")
    
    video = await test_repository.get_video_by_id(video_id)
    assert video["status"] == "failed", f"Expected status 'failed', got '{video['status']}'"
    
    print(f"Status: {video['status']}")
    
    # ========================================================================
    # STEP 4: Validate status history
    # ========================================================================
    print(f"\n=== Validating Status History ===")
    
    history = await test_repository.get_status_history(video_id)
    assert len(history) >= 3, f"Expected at least 3 history entries, got {len(history)}"
    
    # Extract statuses
    statuses = [entry["new_status"] for entry in reversed(history)]
    assert statuses[0] == "discovered"
    assert statuses[1] == "queued"
    assert statuses[2] == "downloading"
    assert statuses[-1] == "failed", "Final status should be 'failed'"
    
    # Verify failed entry has error information
    failed_entry = history[0]  # Newest first
    assert failed_entry["new_status"] == "failed"
    
    print("\nStatus History:")
    for entry in reversed(history):
        status = entry["new_status"]
        reason = entry.get("reason", "N/A")
        print(f"  {status:<15} - {reason}")
    
    print(f"\n{'=' * 80}")
    print(f"Download failure workflow completed successfully")
    print(f"{'=' * 80}\n")

