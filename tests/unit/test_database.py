"""Basic database functionality tests."""

import pytest
import pytest_asyncio
from pathlib import Path

from fuzzbin.common.config import DatabaseConfig
from fuzzbin.core.db import (
    VideoRepository,
    VideoQuery,
    VideoNotFoundError,
    ArtistNotFoundError,
)


@pytest.mark.asyncio
class TestDatabaseBasics:
    """Test basic database operations."""

    async def test_repository_initialization(self, test_repository: VideoRepository):
        """Test repository can be initialized."""
        # Repository is already initialized by the fixture
        assert test_repository is not None
        assert test_repository.db_path is not None
        assert test_repository.db_path.exists()

    async def test_create_video(self, test_repository: VideoRepository):
        """Test creating a video record."""
        video_id = await test_repository.create_video(
            title="Test Video",
            artist="Test Artist",
            year=2020,
        )
        assert video_id > 0

        # Verify video was created
        video = await test_repository.get_video_by_id(video_id)
        assert video["title"] == "Test Video"
        assert video["artist"] == "Test Artist"
        assert video["year"] == 2020

    async def test_get_video_by_id_not_found(self, test_repository: VideoRepository):
        """Test getting non-existent video raises error."""
        with pytest.raises(VideoNotFoundError):
            await test_repository.get_video_by_id(99999)

    async def test_upsert_artist(self, test_repository: VideoRepository):
        """Test creating/updating artist."""
        artist_id = await test_repository.upsert_artist(
            name="Test Artist",
            imvdb_entity_id="test123",
        )
        assert artist_id > 0

        # Update same artist
        artist_id2 = await test_repository.upsert_artist(
            name="Test Artist",
            biography="Updated bio",
        )
        assert artist_id == artist_id2

        # Verify artist was updated
        artist = await test_repository.get_artist_by_id(artist_id)
        assert artist["name"] == "Test Artist"
        assert artist["biography"] == "Updated bio"

    async def test_link_video_artist(self, test_repository: VideoRepository):
        """Test linking video to artist."""
        # Create video and artist
        video_id = await test_repository.create_video(
            title="Collaboration",
            artist="Primary Artist",
        )
        artist_id = await test_repository.upsert_artist(name="Featured Artist")

        # Link them
        await test_repository.link_video_artist(
            video_id=video_id,
            artist_id=artist_id,
            role="featured",
        )

        # Verify link
        artists = await test_repository.get_video_artists(video_id)
        assert len(artists) == 1
        assert artists[0]["name"] == "Featured Artist"
        assert artists[0]["role"] == "featured"

    async def test_soft_delete_and_restore(
        self, test_repository: VideoRepository, sample_video_metadata: dict
    ):
        """Test soft delete and restore functionality."""
        # Create video
        video_id = await test_repository.create_video(**sample_video_metadata)

        # Soft delete
        await test_repository.delete_video(video_id)

        # Should not be found by default
        with pytest.raises(VideoNotFoundError):
            await test_repository.get_video_by_id(video_id)

        # Should be found with include_deleted
        video = await test_repository.get_video_by_id(video_id, include_deleted=True)
        assert video["is_deleted"] == 1

        # Restore
        await test_repository.restore_video(video_id)

        # Should be found again
        video = await test_repository.get_video_by_id(video_id)
        assert video["is_deleted"] == 0

    async def test_query_builder(self, test_repository: VideoRepository):
        """Test fluent query builder."""
        # Create test videos
        await test_repository.create_video(
            title="Rock Video 1", artist="Rock Band", year=2020, genre="Rock"
        )
        await test_repository.create_video(
            title="Rock Video 2", artist="Rock Band", year=2021, genre="Rock"
        )
        await test_repository.create_video(
            title="Pop Video", artist="Pop Star", year=2020, genre="Pop"
        )

        # Query by artist
        results = await test_repository.query().where_artist("Rock Band").execute()
        assert len(results) == 2

        # Query by year
        results = await test_repository.query().where_year(2020).execute()
        assert len(results) == 2

        # Query with chaining
        results = (
            await test_repository.query()
            .where_genre("Rock")
            .where_year_range(2020, 2021)
            .order_by("year")
            .execute()
        )
        assert len(results) == 2
        assert results[0]["year"] <= results[1]["year"]

    async def test_bulk_operations(self, test_repository: VideoRepository):
        """Test bulk create and link operations."""
        # Bulk create videos
        videos = [
            {"title": f"Video {i}", "artist": "Bulk Artist", "year": 2020 + i}
            for i in range(5)
        ]
        video_ids = await test_repository.bulk_create_videos(videos)
        assert len(video_ids) == 5

        # Create artist
        artist_id = await test_repository.upsert_artist(name="Bulk Artist")

        # Bulk link
        await test_repository.bulk_link_artists(
            video_id=video_ids[0],
            artist_links=[
                {"artist_id": artist_id, "role": "primary", "position": 0},
            ],
        )

        # Verify
        artists = await test_repository.get_video_artists(video_ids[0])
        assert len(artists) == 1

    async def test_count_query(self, test_repository: VideoRepository):
        """Test count queries."""
        # Create videos
        await test_repository.create_video(title="Video 1", artist="Artist A")
        await test_repository.create_video(title="Video 2", artist="Artist A")
        await test_repository.create_video(title="Video 3", artist="Artist B")

        # Count all
        total = await test_repository.query().count()
        assert total == 3

        # Count filtered
        count = await test_repository.query().where_artist("Artist A").count()
        assert count == 2

    async def test_update_video(self, test_repository: VideoRepository):
        """Test updating video metadata."""
        video_id = await test_repository.create_video(
            title="Original Title", artist="Artist", year=2020
        )

        # Update
        await test_repository.update_video(
            video_id, title="Updated Title", year=2021
        )

        # Verify
        video = await test_repository.get_video_by_id(video_id)
        assert video["title"] == "Updated Title"
        assert video["year"] == 2021
        assert video["artist"] == "Artist"  # Unchanged

    async def test_transaction(self, test_repository: VideoRepository):
        """Test explicit transaction."""
        async with test_repository.transaction():
            video_id = await test_repository.create_video(
                title="Transaction Video",
                artist="Transaction Artist",
            )
            artist_id = await test_repository.upsert_artist(
                name="Transaction Artist"
            )
            await test_repository.link_video_artist(video_id, artist_id)

        # Verify all operations completed
        video = await test_repository.get_video_by_id(video_id)
        assert video is not None
        artists = await test_repository.get_video_artists(video_id)
        assert len(artists) == 1

    async def test_get_video_by_youtube_id(
        self, test_repository: VideoRepository, sample_video_metadata: dict
    ):
        """Test retrieving video by YouTube ID."""
        await test_repository.create_video(**sample_video_metadata)

        video = await test_repository.get_video_by_youtube_id(
            sample_video_metadata["youtube_id"]
        )
        assert video["title"] == sample_video_metadata["title"]

    async def test_get_video_by_imvdb_id(
        self, test_repository: VideoRepository, sample_video_metadata: dict
    ):
        """Test retrieving video by IMVDb ID."""
        await test_repository.create_video(**sample_video_metadata)

        video = await test_repository.get_video_by_imvdb_id(
            sample_video_metadata["imvdb_video_id"]
        )
        assert video["title"] == sample_video_metadata["title"]

    async def test_relative_paths(self, test_repository: VideoRepository):
        """Test relative path calculation."""
        library_dir = getattr(test_repository, 'library_dir', None)
        if library_dir:
            abs_path = str(library_dir / "videos" / "test.mp4")
            video_id = await test_repository.create_video(
                title="Path Test",
                artist="Artist",
                video_file_path=abs_path,
            )

            video = await test_repository.get_video_by_id(video_id)
            assert video["video_file_path"] == abs_path
            assert video["video_file_path_relative"] == "videos/test.mp4"

@pytest.mark.asyncio
class TestStatusTracking:
    """Test video status tracking functionality."""

    async def test_create_video_with_status(self, test_repository: VideoRepository):
        """Test creating video with initial status."""
        video_id = await test_repository.create_video(
            title="Status Test",
            artist="Artist",
            status="discovered",
            download_source="youtube",
        )

        video = await test_repository.get_video_by_id(video_id)
        assert video["status"] == "discovered"
        assert video["download_source"] == "youtube"
        assert video["status_changed_at"] is not None

        # Verify history was recorded
        history = await test_repository.get_status_history(video_id)
        assert len(history) == 1
        assert history[0]["old_status"] is None
        assert history[0]["new_status"] == "discovered"

    async def test_update_status(self, test_repository: VideoRepository):
        """Test updating video status."""
        video_id = await test_repository.create_video(
            title="Status Update Test",
            artist="Artist",
            status="discovered",
        )

        # Update to queued
        await test_repository.update_status(
            video_id,
            "queued",
            reason="Added to download queue",
            changed_by="test_user",
        )

        video = await test_repository.get_video_by_id(video_id)
        assert video["status"] == "queued"

        # Check history
        history = await test_repository.get_status_history(video_id)
        assert len(history) == 2
        assert history[0]["new_status"] == "queued"
        assert history[0]["old_status"] == "discovered"
        assert history[0]["reason"] == "Added to download queue"

    async def test_status_transition_workflow(self, test_repository: VideoRepository):
        """Test typical status workflow."""
        # Create as discovered
        video_id = await test_repository.create_video(
            title="Workflow Test",
            artist="Artist",
            status="discovered",
        )

        # Queue for download
        await test_repository.update_status(video_id, "queued")

        # Start downloading
        await test_repository.update_status(video_id, "downloading")

        # Mark as downloaded
        await test_repository.mark_as_downloaded(
            video_id,
            file_path="/path/to/video.mp4",
            file_size=12345678,
            file_checksum="abc123",
            download_source="youtube",
        )

        video = await test_repository.get_video_by_id(video_id)
        assert video["status"] == "downloaded"
        assert video["video_file_path"] == "/path/to/video.mp4"
        assert video["file_size"] == 12345678
        assert video["file_checksum"] == "abc123"
        assert video["download_source"] == "youtube"

        # Check complete history
        history = await test_repository.get_status_history(video_id)
        statuses = [h["new_status"] for h in reversed(history)]
        assert statuses == ["discovered", "queued", "downloading", "downloaded"]

    async def test_mark_download_failed(self, test_repository: VideoRepository):
        """Test marking download as failed."""
        video_id = await test_repository.create_video(
            title="Failed Download Test",
            artist="Artist",
            status="downloading",
        )

        await test_repository.mark_download_failed(
            video_id,
            error_message="Network timeout",
        )

        video = await test_repository.get_video_by_id(video_id)
        assert video["status"] == "failed"
        assert video["status_message"] == "Network timeout"
        assert video["last_download_error"] == "Network timeout"
        assert video["download_attempts"] == 1

        # Try again and fail
        await test_repository.mark_download_failed(
            video_id,
            error_message="Connection refused",
        )

        video = await test_repository.get_video_by_id(video_id)
        assert video["download_attempts"] == 2

    async def test_query_by_status(self, test_repository: VideoRepository):
        """Test querying videos by status."""
        # Create videos with different statuses
        vid1 = await test_repository.create_video(
            title="Discovered 1", artist="A", status="discovered"
        )
        vid2 = await test_repository.create_video(
            title="Downloaded 1", artist="B", status="downloaded"
        )
        vid3 = await test_repository.create_video(
            title="Discovered 2", artist="C", status="discovered"
        )

        # Query discovered videos
        discovered = await test_repository.query().where_status("discovered").execute()
        assert len(discovered) == 2
        assert {v["id"] for v in discovered} == {vid1, vid3}

        # Query downloaded videos
        downloaded = await test_repository.query().where_status("downloaded").execute()
        assert len(downloaded) == 1
        assert downloaded[0]["id"] == vid2

    async def test_query_by_download_source(self, test_repository: VideoRepository):
        """Test querying videos by download source."""
        await test_repository.create_video(
            title="YouTube Video", artist="A", download_source="youtube"
        )
        await test_repository.create_video(
            title="Vimeo Video", artist="B", download_source="vimeo"
        )

        youtube_videos = (
            await test_repository.query().where_download_source("youtube").execute()
        )
        assert len(youtube_videos) == 1
        assert youtube_videos[0]["title"] == "YouTube Video"

    async def test_invalid_status(self, test_repository: VideoRepository):
        """Test that invalid status raises error."""
        video_id = await test_repository.create_video(
            title="Invalid Status Test",
            artist="Artist",
        )

        with pytest.raises(ValueError, match="Invalid status"):
            await test_repository.update_status(video_id, "invalid_status")

    async def test_status_unchanged_no_history(self, test_repository: VideoRepository):
        """Test updating to same status doesn't create duplicate history."""
        video_id = await test_repository.create_video(
            title="Same Status Test",
            artist="Artist",
            status="discovered",
        )

        # Update to same status
        await test_repository.update_status(video_id, "discovered")

        history = await test_repository.get_status_history(video_id)
        assert len(history) == 1  # Only initial creation

    async def test_update_video_tracks_status_change(
        self, test_repository: VideoRepository
    ):
        """Test that update_video automatically tracks status changes."""
        video_id = await test_repository.create_video(
            title="Auto Track Test",
            artist="Artist",
            status="discovered",
        )

        # Update status via update_video
        await test_repository.update_video(
            video_id, status="queued", status_message="Queued by scheduler"
        )

        history = await test_repository.get_status_history(video_id)
        assert len(history) == 2
        assert history[0]["new_status"] == "queued"
        assert history[0]["old_status"] == "discovered"