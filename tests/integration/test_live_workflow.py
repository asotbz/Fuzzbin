"""
Live integration test for multi-module workflow.

This test exercises the complete Fuzzbin workflow using real API credentials:
1. Search IMVDb for a music video by artist and track title
2. Get full video details including director, sources, and credits
3. Extract Discogs artist ID from IMVDb entity data
4. Search Discogs for the matching studio album release
5. Generate artist.nfo and musicvideo.nfo XML files
6. Build organized media file paths

SETUP INSTRUCTIONS:
===================
Export the following environment variables with your API credentials:

    export IMVDB_APP_KEY="your-imvdb-api-key"
    export DISCOGS_API_KEY="your-discogs-consumer-key"
    export DISCOGS_API_SECRET="your-discogs-consumer-secret"

RUN INSTRUCTIONS:
=================
Run this test with:

    pytest tests/integration/test_live_workflow.py -v -s

Or run all live tests:

    pytest -m live -v -s

To exclude live tests (e.g., in CI):

    pytest -m "not live"

NOTES:
======
- This test uses real API endpoints and credentials
- Cache databases are isolated to temporary directories per test run
- DEBUG logging is enabled to show rate limiting, caching, and HTTP details
- Test will be skipped if required environment variables are not set
"""

import os
from pathlib import Path

import pytest
import pytest_asyncio

from fuzzbin.common.config import Config
from fuzzbin.api.imvdb_client import IMVDbClient
from fuzzbin.api.discogs_client import DiscogsClient
from fuzzbin.parsers import (
    ArtistNFO,
    MusicVideoNFO,
    ArtistNFOParser,
    MusicVideoNFOParser,
    FeaturedArtistConfig,
    DiscogsParser,
)
from fuzzbin.core import build_media_paths


@pytest.fixture
def test_cache_dir(tmp_path: Path) -> Path:
    """Create and return a temporary cache directory for isolated test runs."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


@pytest.fixture
def clean_test_config(test_cache_dir: Path) -> Config:
    """
    Load config.yaml and modify it for clean test environment.
    
    - Sets logging level to DEBUG for verbose output
    - Redirects cache databases to temporary directory
    - Environment variables still override API credentials
    """
    # Load base config from project root
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    config = Config.from_yaml(config_path)
    
    # Enable DEBUG logging
    config.logging.level = "DEBUG"
    
    # Redirect cache databases to temporary directory
    if "imvdb" in config.apis:
        config.apis["imvdb"].cache.storage_path = str(
            test_cache_dir / "imvdb_test.db"
        )
    if "discogs" in config.apis:
        config.apis["discogs"].cache.storage_path = str(
            test_cache_dir / "discogs_test.db"
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


@pytest.mark.live
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
    tmp_path: Path,
):
    """
    Test complete workflow from search to NFO generation.
    
    This test validates the entire data pipeline:
    - IMVDb video search and detail retrieval
    - Discogs ID extraction from IMVDb entity
    - Discogs master release lookup
    - NFO file generation (artist.nfo and musicvideo.nfo)
    - Organized media path generation
    
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
    else:
        print("No primary YouTube source found")
    
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
    
    print(f"\n{'=' * 80}")
    print(f"Workflow completed successfully for: {artist} - {track}")
    print(f"{'=' * 80}\n")
