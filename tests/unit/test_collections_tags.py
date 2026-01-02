"""Tests for collections and tags functionality."""

import pytest
import pytest_asyncio

from fuzzbin.core.db import VideoRepository, QueryError


@pytest.mark.asyncio
class TestCollections:
    """Test collection CRUD operations."""

    async def test_upsert_collection(self, test_repository: VideoRepository):
        """Test creating and updating collections."""
        # Create new collection
        collection_id = await test_repository.upsert_collection(
            name="Greatest Hits",
            description="The best music videos",
        )
        assert collection_id > 0

        # Get collection
        collection = await test_repository.get_collection_by_id(collection_id)
        assert collection["name"] == "Greatest Hits"
        assert collection["description"] == "The best music videos"
        assert collection["is_deleted"] == 0

        # Update collection (case-insensitive name match)
        collection_id2 = await test_repository.upsert_collection(
            name="greatest hits",  # Different case
            description="Updated description",
        )
        assert collection_id == collection_id2

        # Verify update
        collection = await test_repository.get_collection_by_id(collection_id)
        assert collection["description"] == "Updated description"

    async def test_list_collections(self, test_repository: VideoRepository):
        """Test listing collections."""
        # Create multiple collections
        await test_repository.upsert_collection(name="90s Hits")
        await test_repository.upsert_collection(name="Alternative Rock")
        await test_repository.upsert_collection(name="Best of 2020s")

        collections = await test_repository.list_collections()
        assert len(collections) >= 3
        names = [c["name"] for c in collections]
        assert "90s Hits" in names
        assert "Alternative Rock" in names


@pytest.mark.asyncio
class TestVideoCollections:
    """Test video-collection relationship operations."""

    async def test_link_video_to_collection(self, test_repository: VideoRepository):
        """Test linking a video to a collection."""
        # Create video and collection
        video_id = await test_repository.create_video(
            title="Test Video", artist="Test Artist"
        )
        collection_id = await test_repository.upsert_collection(name="My Playlist")

        # Link them
        await test_repository.link_video_collection(
            video_id=video_id, collection_id=collection_id, position=0
        )

        # Verify link
        collections = await test_repository.get_video_collections(video_id)
        assert len(collections) == 1
        assert collections[0]["name"] == "My Playlist"
        assert collections[0]["position"] == 0

    async def test_get_collection_videos(self, test_repository: VideoRepository):
        """Test getting all videos in a collection."""
        # Create collection
        collection_id = await test_repository.upsert_collection(name="Top Videos")

        # Create videos
        video_id1 = await test_repository.create_video(
            title="Video 1", artist="Artist A"
        )
        video_id2 = await test_repository.create_video(
            title="Video 2", artist="Artist B"
        )
        video_id3 = await test_repository.create_video(
            title="Video 3", artist="Artist C"
        )

        # Link with different positions
        await test_repository.link_video_collection(video_id1, collection_id, position=2)
        await test_repository.link_video_collection(video_id2, collection_id, position=0)
        await test_repository.link_video_collection(video_id3, collection_id, position=1)

        # Get videos (should be ordered by position)
        videos = await test_repository.get_collection_videos(
            collection_id, order_by_position=True
        )
        assert len(videos) == 3
        assert videos[0]["title"] == "Video 2"  # position 0
        assert videos[1]["title"] == "Video 3"  # position 1
        assert videos[2]["title"] == "Video 1"  # position 2

    async def test_duplicate_link_ignored(self, test_repository: VideoRepository):
        """Test that duplicate links are ignored."""
        video_id = await test_repository.create_video(
            title="Test", artist="Test Artist"
        )
        collection_id = await test_repository.upsert_collection(name="Test Collection")

        # Link twice
        await test_repository.link_video_collection(video_id, collection_id)
        await test_repository.link_video_collection(video_id, collection_id)

        # Should only have one link
        collections = await test_repository.get_video_collections(video_id)
        assert len(collections) == 1


@pytest.mark.asyncio
class TestTags:
    """Test tag CRUD operations."""

    async def test_upsert_tag(self, test_repository: VideoRepository):
        """Test creating tags."""
        # Create new tag
        tag_id = await test_repository.upsert_tag(name="rock")
        assert tag_id > 0

        # Get tag
        tag = await test_repository.get_tag_by_id(tag_id)
        assert tag["name"] == "rock"
        assert tag["normalized_name"] == "rock"
        assert tag["usage_count"] == 0

        # Same tag with different case should return same ID
        tag_id2 = await test_repository.upsert_tag(name="Rock")
        assert tag_id == tag_id2

    async def test_tag_normalization(self, test_repository: VideoRepository):
        """Test tag name normalization."""
        # With normalization (default)
        tag_id1 = await test_repository.upsert_tag(name="Alternative Rock", normalize=True)
        tag = await test_repository.get_tag_by_id(tag_id1)
        assert tag["normalized_name"] == "alternative rock"

        # Different case should be same tag
        tag_id2 = await test_repository.upsert_tag(name="ALTERNATIVE ROCK", normalize=True)
        assert tag_id1 == tag_id2

    async def test_list_tags(self, test_repository: VideoRepository):
        """Test listing tags."""
        # Create multiple tags
        await test_repository.upsert_tag(name="pop")
        await test_repository.upsert_tag(name="rock")
        await test_repository.upsert_tag(name="jazz")

        tags = await test_repository.list_tags()
        assert len(tags) >= 3
        names = [t["name"] for t in tags]
        assert "pop" in names
        assert "rock" in names
        assert "jazz" in names


@pytest.mark.asyncio
class TestVideoTags:
    """Test video-tag relationship operations."""

    async def test_add_video_tag(self, test_repository: VideoRepository):
        """Test adding a tag to a video."""
        # Create video and tag
        video_id = await test_repository.create_video(title="Test", artist="Artist")
        tag_id = await test_repository.upsert_tag(name="90s")

        # Add tag
        await test_repository.add_video_tag(video_id, tag_id, source="manual")

        # Verify tag added
        tags = await test_repository.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "90s"
        assert tags[0]["source"] == "manual"
        assert tags[0]["usage_count"] == 1

    async def test_remove_video_tag(self, test_repository: VideoRepository):
        """Test removing a tag from a video."""
        video_id = await test_repository.create_video(title="Test", artist="Artist")
        tag_id = await test_repository.upsert_tag(name="temporary")

        # Add tag
        await test_repository.add_video_tag(video_id, tag_id)

        # Verify added
        tags = await test_repository.get_video_tags(video_id)
        assert len(tags) == 1

        # Remove tag
        await test_repository.remove_video_tag(video_id, tag_id)

        # Verify removed
        tags = await test_repository.get_video_tags(video_id)
        assert len(tags) == 0

    async def test_tag_usage_count_trigger(self, test_repository: VideoRepository):
        """Test that usage_count is incremented/decremented automatically."""
        video_id = await test_repository.create_video(title="Test", artist="Artist")
        tag_id = await test_repository.upsert_tag(name="popular")

        # Initially 0
        tag = await test_repository.get_tag_by_id(tag_id)
        assert tag["usage_count"] == 0

        # Add tag to video
        await test_repository.add_video_tag(video_id, tag_id)

        # Should increment
        tag = await test_repository.get_tag_by_id(tag_id)
        assert tag["usage_count"] == 1

        # Remove tag
        await test_repository.remove_video_tag(video_id, tag_id)

        # Tag should be auto-deleted when usage_count reaches 0
        # We verify by trying to get it - it should raise TagNotFoundError
        from fuzzbin.core.db import TagNotFoundError
        with pytest.raises(TagNotFoundError):
            await test_repository.get_tag_by_id(tag_id)

    async def test_get_tag_videos(self, test_repository: VideoRepository):
        """Test getting all videos with a specific tag."""
        # Create videos
        video_id1 = await test_repository.create_video(title="Video 1", artist="Artist A")
        video_id2 = await test_repository.create_video(title="Video 2", artist="Artist B")
        video_id3 = await test_repository.create_video(title="Video 3", artist="Artist C")

        # Create tag
        tag_id = await test_repository.upsert_tag(name="featured")

        # Add tag to some videos
        await test_repository.add_video_tag(video_id1, tag_id)
        await test_repository.add_video_tag(video_id3, tag_id)

        # Get videos with tag
        videos = await test_repository.get_tag_videos(tag_id)
        assert len(videos) == 2
        titles = [v["title"] for v in videos]
        assert "Video 1" in titles
        assert "Video 3" in titles
        assert "Video 2" not in titles


@pytest.mark.asyncio
class TestAutoDecadeTag:
    """Test automatic decade tag generation."""

    async def test_auto_add_decade_tag_90s(self, test_repository: VideoRepository):
        """Test auto-generating decade tag for 1990s."""
        video_id = await test_repository.create_video(
            title="Smells Like Teen Spirit", artist="Nirvana", year=1991
        )

        tag_id = await test_repository.auto_add_decade_tag(video_id, 1991)
        assert tag_id is not None

        # Verify tag created and added
        tags = await test_repository.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "90s"
        assert tags[0]["source"] == "auto"

    async def test_auto_add_decade_tag_2000s(self, test_repository: VideoRepository):
        """Test auto-generating decade tag for 2000s."""
        video_id = await test_repository.create_video(
            title="Crazy", artist="Gnarls Barkley", year=2006
        )

        tag_id = await test_repository.auto_add_decade_tag(video_id, 2006)

        tags = await test_repository.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "00s"

    async def test_auto_add_decade_tag_2010s(self, test_repository: VideoRepository):
        """Test auto-generating decade tag for 2010s."""
        video_id = await test_repository.create_video(
            title="Blurred Lines", artist="Robin Thicke", year=2013
        )

        tag_id = await test_repository.auto_add_decade_tag(video_id, 2013)

        tags = await test_repository.get_video_tags(video_id)
        assert tags[0]["name"] == "10s"

    async def test_auto_add_decade_tag_custom_format(self, test_repository: VideoRepository):
        """Test auto-generating decade tag with custom format."""
        video_id = await test_repository.create_video(
            title="Test", artist="Test Artist", year=1985
        )

        tag_id = await test_repository.auto_add_decade_tag(
            video_id, 1985, tag_format="decade-{decade}"
        )

        tags = await test_repository.get_video_tags(video_id)
        assert tags[0]["name"] == "decade-80"

    async def test_auto_add_decade_tag_invalid_year(self, test_repository: VideoRepository):
        """Test that invalid years are handled gracefully."""
        video_id = await test_repository.create_video(title="Test", artist="Test Artist")

        # Invalid years should return None
        tag_id = await test_repository.auto_add_decade_tag(video_id, 1800)
        assert tag_id is None

        tag_id = await test_repository.auto_add_decade_tag(video_id, 2200)
        assert tag_id is None

        tag_id = await test_repository.auto_add_decade_tag(video_id, None)
        assert tag_id is None


@pytest.mark.asyncio
class TestTagQueries:
    """Test VideoQuery filters for tags and collections."""

    async def test_where_tag(self, test_repository: VideoRepository):
        """Test filtering videos by tag."""
        # Create videos with tags
        video_id1 = await test_repository.create_video(title="Video 1", artist="Artist")
        video_id2 = await test_repository.create_video(title="Video 2", artist="Artist")
        video_id3 = await test_repository.create_video(title="Video 3", artist="Artist")

        # Add tags manually
        rock_id = await test_repository.upsert_tag("rock")
        alt_id = await test_repository.upsert_tag("alternative")
        pop_id = await test_repository.upsert_tag("pop")
        electronic_id = await test_repository.upsert_tag("electronic")
        grunge_id = await test_repository.upsert_tag("grunge")

        await test_repository.add_video_tag(video_id1, rock_id)
        await test_repository.add_video_tag(video_id1, alt_id)
        await test_repository.add_video_tag(video_id2, pop_id)
        await test_repository.add_video_tag(video_id2, electronic_id)
        await test_repository.add_video_tag(video_id3, rock_id)
        await test_repository.add_video_tag(video_id3, grunge_id)

        # Query by tag
        results = await test_repository.query().where_tag("rock").execute()
        assert len(results) == 2
        titles = [v["title"] for v in results]
        assert "Video 1" in titles
        assert "Video 3" in titles

    async def test_where_collection(self, test_repository: VideoRepository):
        """Test filtering videos by collection."""
        # Create collection and videos
        collection_id = await test_repository.upsert_collection(name="My Favorites")
        video_id1 = await test_repository.create_video(title="Fav 1", artist="Artist")
        video_id2 = await test_repository.create_video(title="Fav 2", artist="Artist")
        video_id3 = await test_repository.create_video(title="Not Fav", artist="Artist")

        # Add to collection
        await test_repository.link_video_collection(video_id1, collection_id)
        await test_repository.link_video_collection(video_id2, collection_id)

        # Query by collection
        results = await test_repository.query().where_collection("Favorites").execute()
        assert len(results) == 2
        titles = [v["title"] for v in results]
        assert "Fav 1" in titles
        assert "Fav 2" in titles
        assert "Not Fav" not in titles

    async def test_combined_filters(self, test_repository: VideoRepository):
        """Test combining tag and collection filters."""
        collection_id = await test_repository.upsert_collection(name="Rock Collection")

        video_id1 = await test_repository.create_video(title="Rock 90s", artist="Artist", year=1995)
        video_id2 = await test_repository.create_video(title="Rock 00s", artist="Artist", year=2005)
        video_id3 = await test_repository.create_video(title="Pop 90s", artist="Artist", year=1998)

        # Add tags manually
        rock_id = await test_repository.upsert_tag("rock")
        nineties_id = await test_repository.upsert_tag("90s")
        zeroes_id = await test_repository.upsert_tag("00s")
        pop_id = await test_repository.upsert_tag("pop")

        await test_repository.add_video_tag(video_id1, rock_id)
        await test_repository.add_video_tag(video_id1, nineties_id)
        await test_repository.add_video_tag(video_id2, rock_id)
        await test_repository.add_video_tag(video_id2, zeroes_id)
        await test_repository.add_video_tag(video_id3, pop_id)
        await test_repository.add_video_tag(video_id3, nineties_id)

        await test_repository.link_video_collection(video_id1, collection_id)
        await test_repository.link_video_collection(video_id2, collection_id)

        # Rock collection + 90s tag
        results = (
            await test_repository.query()
            .where_collection("Rock Collection")
            .where_tag("90s")
            .execute()
        )
        assert len(results) == 1
        assert results[0]["title"] == "Rock 90s"


@pytest.mark.asyncio
class TestNFOExportWithTags:
    """Test NFO export includes tags from database."""

    async def test_export_video_with_tags(self, test_repository: VideoRepository, tmp_path):
        """Test that NFO export includes tags from database."""
        from fuzzbin.core.db.exporter import NFOExporter
        from fuzzbin.parsers.musicvideo_parser import MusicVideoNFOParser

        # Create video with tags
        video_id = await test_repository.create_video(
            title="Test Video",
            artist="Test Artist",
            year=1995,
        )
        # Add tags manually
        rock_id = await test_repository.upsert_tag("rock")
        alt_id = await test_repository.upsert_tag("alternative")
        nineties_id = await test_repository.upsert_tag("90s")
        await test_repository.add_video_tag(video_id, rock_id)
        await test_repository.add_video_tag(video_id, alt_id)
        await test_repository.add_video_tag(video_id, nineties_id)

        # Export to NFO
        exporter = NFOExporter(test_repository)
        nfo_path = tmp_path / "musicvideo.nfo"
        exported_path = await exporter.export_video_to_nfo(video_id, nfo_path)

        # Read back NFO and verify tags
        parser = MusicVideoNFOParser()
        nfo = parser.parse_file(exported_path)

        assert len(nfo.tags) == 3
        assert "rock" in nfo.tags
        assert "alternative" in nfo.tags
        assert "90s" in nfo.tags
