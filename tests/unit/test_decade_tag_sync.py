"""Tests for auto-decade tag synchronization feature."""

import pytest


@pytest.mark.asyncio
class TestDecadeTagRepositoryMethods:
    """Test repository methods for decade tag management."""

    async def test_remove_auto_decade_tags_with_default_pattern(self, test_db):
        """Test removing auto-decade tags with default pattern."""
        # Create video with year
        video_id = await test_db.create_video(
            title="Test Video",
            artist="Test Artist",
            year=1991,
        )

        # Add some tags
        tag1_id = await test_db.upsert_tag("90s", normalize=True)
        tag2_id = await test_db.upsert_tag("rock", normalize=True)
        tag3_id = await test_db.upsert_tag("00s", normalize=True)

        await test_db.add_video_tag(video_id, tag1_id, source="auto")
        await test_db.add_video_tag(video_id, tag2_id, source="manual")
        await test_db.add_video_tag(video_id, tag3_id, source="auto")

        # Remove auto decade tags
        removed = await test_db.remove_auto_decade_tags(video_id)

        # Should remove both "90s" and "00s" (auto tags matching pattern)
        assert removed == 2

        # Verify only "rock" remains
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "rock"

    async def test_remove_auto_decade_tags_with_custom_format(self, test_db):
        """Test removing auto-decade tags with custom format pattern."""
        video_id = await test_db.create_video(
            title="Test Video",
            artist="Test Artist",
            year=1985,
        )

        # Add tags with custom format
        tag1_id = await test_db.upsert_tag("decade-80", normalize=True)
        tag2_id = await test_db.upsert_tag("80s", normalize=True)

        await test_db.add_video_tag(video_id, tag1_id, source="auto")
        await test_db.add_video_tag(video_id, tag2_id, source="manual")

        # Remove only tags matching custom format
        removed = await test_db.remove_auto_decade_tags(video_id, old_format="decade-{decade}")

        # Should remove only "decade-80"
        assert removed == 1

        # Verify "80s" remains
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "80s"

    async def test_remove_auto_decade_tags_only_removes_auto_source(self, test_db):
        """Test that removal only affects tags with source='auto'."""
        video_id = await test_db.create_video(
            title="Test Video",
            artist="Test Artist",
            year=2006,
        )

        # Add same tag with different sources
        tag_id = await test_db.upsert_tag("00s", normalize=True)
        await test_db.add_video_tag(video_id, tag_id, source="manual")

        # Try to remove auto decade tags
        removed = await test_db.remove_auto_decade_tags(video_id)

        # Should not remove manual tag
        assert removed == 0

        # Verify tag still exists
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "00s"

    async def test_update_decade_tag_same_decade(self, test_db):
        """Test update_decade_tag when years are in same decade."""
        video_id = await test_db.create_video(
            title="Test Video",
            artist="Test Artist",
            year=1991,
        )

        # Add decade tag
        await test_db.auto_add_decade_tag(video_id, 1991)

        # Update to another year in same decade
        updated = await test_db.update_decade_tag(video_id, 1991, 1995)

        # Should not update (same decade)
        assert updated is False

        # Verify still has "90s" tag
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "90s"

    async def test_update_decade_tag_different_decade(self, test_db):
        """Test update_decade_tag when year changes to different decade."""
        video_id = await test_db.create_video(
            title="Test Video",
            artist="Test Artist",
            year=1991,
        )

        # Add decade tag for 90s
        await test_db.auto_add_decade_tag(video_id, 1991)

        # Update to 2000s
        updated = await test_db.update_decade_tag(video_id, 1991, 2006)

        # Should update
        assert updated is True

        # Verify has "00s" tag, not "90s"
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "00s"

    async def test_update_decade_tag_no_old_year(self, test_db):
        """Test update_decade_tag when video previously had no year."""
        video_id = await test_db.create_video(
            title="Test Video",
            artist="Test Artist",
        )

        # Update from None to 2013
        updated = await test_db.update_decade_tag(video_id, None, 2013)

        # Should update (add new tag)
        assert updated is True

        # Verify has "10s" tag
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "10s"

    async def test_update_decade_tag_with_custom_format(self, test_db):
        """Test update_decade_tag with custom format."""
        video_id = await test_db.create_video(
            title="Test Video",
            artist="Test Artist",
            year=1985,
        )

        # Add decade tag with custom format
        custom_format = "decade-{decade}"
        await test_db.auto_add_decade_tag(video_id, 1985, tag_format=custom_format)

        # Update to different decade
        updated = await test_db.update_decade_tag(video_id, 1985, 1995, tag_format=custom_format)

        # Should update
        assert updated is True

        # Verify has "decade-90", not "decade-80"
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "decade-90"


@pytest.mark.asyncio
class TestDecadeTagSyncHandler:
    """Test the decade tag sync job handler - simplified tests without handler execution."""

    async def test_decade_tag_operations_prepare_for_sync(self, test_db):
        """Test that decade tag operations work correctly for sync scenarios."""
        # Create videos with years
        video1_id = await test_db.create_video(title="Video 1", artist="Artist 1", year=1991)
        video2_id = await test_db.create_video(title="Video 2", artist="Artist 2", year=2006)
        video3_id = await test_db.create_video(
            title="Video 3",
            artist="Artist 3",  # No year
        )

        # Apply decade tags like sync job would
        await test_db.auto_add_decade_tag(video1_id, 1991, tag_format="{decade}s")
        await test_db.auto_add_decade_tag(video2_id, 2006, tag_format="{decade}s")

        # Verify tags applied
        tags1 = await test_db.get_video_tags(video1_id)
        assert any(t["name"] == "90s" for t in tags1)

        tags2 = await test_db.get_video_tags(video2_id)
        assert any(t["name"] == "00s" for t in tags2)

        # Video without year should have no tags
        tags3 = await test_db.get_video_tags(video3_id)
        assert len(tags3) == 0

    async def test_decade_tag_removal_for_sync(self, test_db):
        """Test removing decade tags like sync job would."""
        # Create video with auto decade tag
        video_id = await test_db.create_video(title="Video", artist="Artist", year=1991)
        await test_db.auto_add_decade_tag(video_id, 1991)

        # Verify tag exists
        tags_before = await test_db.get_video_tags(video_id)
        assert len(tags_before) == 1

        # Remove like sync job would
        removed = await test_db.remove_auto_decade_tags(video_id, old_format="{decade}s")
        assert removed == 1

        # Verify tag removed
        tags_after = await test_db.get_video_tags(video_id)
        assert len(tags_after) == 0

    async def test_decade_tag_migration_for_sync(self, test_db):
        """Test migrating decade tag format like sync job would."""
        # Create video with old format tag
        video_id = await test_db.create_video(title="Video", artist="Artist", year=1985)
        old_format = "{decade}s"
        await test_db.auto_add_decade_tag(video_id, 1985, tag_format=old_format)

        # Migrate like sync job would
        new_format = "decade-{decade}"
        removed = await test_db.remove_auto_decade_tags(video_id, old_format=old_format)
        assert removed == 1

        await test_db.auto_add_decade_tag(video_id, 1985, tag_format=new_format)

        # Verify new format tag exists
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "decade-80"


@pytest.mark.asyncio
class TestVideoServiceDecadeTagUpdate:
    """Test VideoService decade tag updates on year changes."""

    async def test_repository_decade_tag_update_flow(self, test_db):
        """Test repository's decade tag update when year changes."""
        # Create video with year
        video_id = await test_db.create_video(
            title="Video", artist="Artist", year=1985, file_path="/test/video.mp4"
        )
        await test_db.auto_add_decade_tag(video_id, 1985)

        # Verify 80s tag exists
        tags_before = await test_db.get_video_tags(video_id)
        assert any(t["name"] == "80s" for t in tags_before)

        # Simulate what VideoService.update() would do when year changes
        updated = await test_db.update_decade_tag(
            video_id, old_year=1985, new_year=1995, tag_format="{decade}s"
        )
        assert updated is True

        # Verify 80s removed and 90s added
        tags_after = await test_db.get_video_tags(video_id)
        assert not any(t["name"] == "80s" for t in tags_after)
        assert any(t["name"] == "90s" for t in tags_after)

    async def test_repository_decade_tag_removal_flow(self, test_db):
        """Test repository's decade tag removal when year is removed."""
        # Create video with year and decade tag
        video_id = await test_db.create_video(
            title="Video", artist="Artist", year=1985, file_path="/test/video.mp4"
        )
        await test_db.auto_add_decade_tag(video_id, 1985)

        # Verify tag exists
        tags_before = await test_db.get_video_tags(video_id)
        assert any(t["name"] == "80s" for t in tags_before)

        # Simulate what VideoService.update() would do when year removed
        removed = await test_db.remove_auto_decade_tags(video_id)
        assert removed == 1

        # Verify tag removed
        tags_after = await test_db.get_video_tags(video_id)
        assert not any(t["name"] == "80s" for t in tags_after)
