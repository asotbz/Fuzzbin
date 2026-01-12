"""Integration tests for auto_decade tag feature.

Tests the complete end-to-end flow of the decade tag feature.
"""

import pytest

import fuzzbin
from fuzzbin.tasks.models import Job, JobType, JobStatus
from fuzzbin.tasks.handlers import handle_sync_decade_tags


@pytest.fixture(autouse=True)
async def mock_repository(test_db, monkeypatch):
    """Mock fuzzbin.get_repository() to return test database."""
    async def get_test_repo():
        return test_db
    
    monkeypatch.setattr(fuzzbin, "get_repository", get_test_repo)
    yield


@pytest.mark.asyncio
class TestDecadeTagIntegration:
    """End-to-end integration tests for auto_decade tag feature."""

    async def test_enable_auto_decade_applies_tags_to_library(self, test_db):
        """Test enabling auto_decade applies decade tags across the entire library."""
        # Create a library of videos spanning multiple decades
        videos = []
        years = [1975, 1984, 1991, 1999, 2005, 2012, 2020]
        
        for year in years:
            video_id = await test_db.create_video(
                title=f"Video from {year}",
                artist="Test Artist",
                year=year,
                file_path=f"/test/video_{year}.mp4"
            )
            videos.append((video_id, year))

        # Also create a video without a year
        no_year_id = await test_db.create_video(
            title="Video No Year",
            artist="Test Artist",
            file_path="/test/video_no_year.mp4"
        )

        # Verify no decade tags exist initially
        for video_id, _ in videos:
            tags = await test_db.get_video_tags(video_id)
            assert len(tags) == 0

        # Simulate enabling auto_decade by running sync job in "apply" mode
        job = Job(
            id="apply-job",
            type=JobType.SYNC_DECADE_TAGS,
            status=JobStatus.RUNNING,
            metadata={
                "mode": "apply",
                "new_format": "{decade}s"
            }
        )

        await handle_sync_decade_tags(job)

        # Verify job completed successfully
        assert job.status == JobStatus.COMPLETED
        assert job.result["videos_processed"] == len(videos)
        assert job.result["tags_added"] == len(videos)

        # Verify correct decade tags applied
        expected_decades = {
            1975: "70s", 1984: "80s", 1991: "90s", 1999: "90s",
            2005: "00s", 2012: "10s", 2020: "20s"
        }
        
        for video_id, year in videos:
            tags = await test_db.get_video_tags(video_id)
            assert len(tags) == 1
            assert tags[0]["name"] == expected_decades[year]
            assert tags[0]["source"] == "auto"

        # Verify video without year has no tags
        tags = await test_db.get_video_tags(no_year_id)
        assert len(tags) == 0

    async def test_disable_auto_decade_removes_tags_from_library(self, test_db):
        """Test disabling auto_decade removes all auto decade tags."""
        # Create videos with decade tags
        videos = []
        years = [1985, 1995, 2005]
        
        for year in years:
            video_id = await test_db.create_video(
                title=f"Video from {year}",
                artist="Test Artist",
                year=year,
                file_path=f"/test/video_{year}.mp4"
            )
            await test_db.auto_add_decade_tag(video_id, year)
            videos.append(video_id)

        # Add a manual decade tag by directly inserting (simulating manual user addition)
        manual_video_id = await test_db.create_video(
            title="Manual Tag Video",
            artist="Test Artist",
            year=1985,
            file_path="/test/manual.mp4"
        )
        # Add tag with source='manual'
        eighties_tag_id = await test_db.upsert_tag("80s")
        await test_db.add_video_tag(manual_video_id, eighties_tag_id, source="manual")

        # Verify all videos have tags
        for video_id in videos:
            tags = await test_db.get_video_tags(video_id)
            assert len(tags) == 1

        manual_tags = await test_db.get_video_tags(manual_video_id)
        assert len(manual_tags) == 1

        # Simulate disabling auto_decade by running sync job in "remove" mode
        job = Job(
            id="remove-job",
            type=JobType.SYNC_DECADE_TAGS,
            status=JobStatus.RUNNING,
            metadata={
                "mode": "remove",
                "old_format": "{decade}s"
            }
        )

        await handle_sync_decade_tags(job)

        # Verify job completed
        assert job.status == JobStatus.COMPLETED
        assert job.result["tags_removed"] == len(videos)

        # Verify auto tags removed
        for video_id in videos:
            tags = await test_db.get_video_tags(video_id)
            assert len(tags) == 0

        # Verify manual tag still exists
        manual_tags = await test_db.get_video_tags(manual_video_id)
        assert len(manual_tags) == 1
        assert manual_tags[0]["source"] == "manual"

    async def test_change_format_migrates_existing_tags(self, test_db):
        """Test changing decade format migrates all existing tags."""
        # Create videos with old format decade tags
        videos = []
        years = [1985, 1995, 2005]
        old_format = "{decade}s"
        new_format = "decade-{decade}"
        
        for year in years:
            video_id = await test_db.create_video(
                title=f"Video from {year}",
                artist="Test Artist",
                year=year,
                file_path=f"/test/video_{year}.mp4"
            )
            await test_db.auto_add_decade_tag(video_id, year, tag_format=old_format)
            videos.append((video_id, year))

        # Verify old format tags exist
        for video_id, year in videos:
            tags = await test_db.get_video_tags(video_id)
            assert len(tags) == 1
            decade = str((year // 10) % 10) + "0"
            assert tags[0]["name"] == f"{decade}s"

        # Simulate format change by running sync job in "migrate" mode
        job = Job(
            id="migrate-job",
            type=JobType.SYNC_DECADE_TAGS,
            status=JobStatus.RUNNING,
            metadata={
                "mode": "migrate",
                "old_format": old_format,
                "new_format": new_format
            }
        )

        await handle_sync_decade_tags(job)

        # Verify job completed
        assert job.status == JobStatus.COMPLETED
        assert job.result["videos_processed"] == len(videos)
        assert job.result["tags_removed"] == len(videos)
        assert job.result["tags_added"] == len(videos)

        # Verify new format tags exist
        expected_new_tags = {
            1985: "decade-80", 1995: "decade-90", 2005: "decade-00"
        }
        
        for video_id, year in videos:
            tags = await test_db.get_video_tags(video_id)
            assert len(tags) == 1
            assert tags[0]["name"] == expected_new_tags[year]
            assert tags[0]["source"] == "auto"

    async def test_video_year_update_updates_decade_tag(self, test_db):
        """Test that updating a video's year properly updates its decade tag."""
        # Create video with year and decade tag
        video_id = await test_db.create_video(
            title="Test Video",
            artist="Test Artist",
            year=1985,
            file_path="/test/video.mp4"
        )
        await test_db.auto_add_decade_tag(video_id, 1985)

        # Verify 80s tag exists
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "80s"

        # Update year to different decade (simulating what VideoService does)
        updated = await test_db.update_decade_tag(
            video_id,
            old_year=1985,
            new_year=1995,
            tag_format="{decade}s"
        )
        assert updated is True

        # Verify 90s tag now exists instead of 80s
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "90s"
        assert tags[0]["source"] == "auto"

    async def test_video_year_removal_removes_decade_tag(self, test_db):
        """Test that removing a video's year removes its decade tag."""
        # Create video with year and decade tag
        video_id = await test_db.create_video(
            title="Test Video",
            artist="Test Artist",
            year=1985,
            file_path="/test/video.mp4"
        )
        await test_db.auto_add_decade_tag(video_id, 1985)

        # Verify tag exists
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 1

        # Remove decade tag (simulating what VideoService does when year is removed)
        removed = await test_db.remove_auto_decade_tags(video_id)
        assert removed == 1

        # Verify tag is gone
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 0

    async def test_mixed_manual_and_auto_tags_preserved(self, test_db):
        """Test that manual tags are preserved during auto tag operations."""
        # Create video with both auto and manual decade tags
        video_id = await test_db.create_video(
            title="Test Video",
            artist="Test Artist",
            year=1985,
            file_path="/test/video.mp4"
        )
        
        # Add auto decade tag
        await test_db.auto_add_decade_tag(video_id, 1985)
        
        # Add manual tags
        classics_tag_id = await test_db.upsert_tag("classics")
        retro_tag_id = await test_db.upsert_tag("retro")
        await test_db.add_video_tag(video_id, classics_tag_id, source="manual")
        await test_db.add_video_tag(video_id, retro_tag_id, source="manual")

        # Verify 3 tags exist
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 3
        tag_names = {t["name"] for t in tags}
        assert tag_names == {"80s", "classics", "retro"}

        # Remove auto decade tags
        removed = await test_db.remove_auto_decade_tags(video_id)
        assert removed == 1

        # Verify only manual tags remain
        tags = await test_db.get_video_tags(video_id)
        assert len(tags) == 2
        tag_names = {t["name"] for t in tags}
        assert tag_names == {"classics", "retro"}
        
        # Verify all remaining tags are manual
        for tag in tags:
            assert tag["source"] == "manual"

    async def test_custom_decade_formats(self, test_db):
        """Test that custom decade formats work correctly."""
        # Test various custom formats
        formats = [
            ("{decade}s", 1985, "80s"),
            ("decade-{decade}", 1985, "decade-80"),
            ("{decade}0s", 1985, "800s"),
            ("the{decade}s", 1995, "the90s"),
        ]

        for fmt, year, expected_tag in formats:
            # Create video
            video_id = await test_db.create_video(
                title=f"Video {fmt}",
                artist="Test Artist",
                year=year,
                file_path=f"/test/video_{fmt}.mp4"
            )
            
            # Apply decade tag with custom format
            await test_db.auto_add_decade_tag(video_id, year, tag_format=fmt)
            
            # Verify correct tag created
            tags = await test_db.get_video_tags(video_id)
            assert len(tags) == 1
            assert tags[0]["name"] == expected_tag
            assert tags[0]["source"] == "auto"

    async def test_job_cancellation_stops_sync(self, test_db):
        """Test that cancelling a sync job stops processing."""
        # Create many videos
        for i in range(10):
            await test_db.create_video(
                title=f"Video {i}",
                artist="Test Artist",
                year=1985,
                file_path=f"/test/video_{i}.mp4"
            )

        # Create job that's already cancelled
        job = Job(
            id="cancelled-job",
            type=JobType.SYNC_DECADE_TAGS,
            status=JobStatus.CANCELLED,
            metadata={
                "mode": "apply",
                "new_format": "{decade}s"
            }
        )

        # Run handler - should exit immediately
        await handle_sync_decade_tags(job)

        # Job should remain cancelled with no result
        assert job.status == JobStatus.CANCELLED
        assert job.result is None

    async def test_batch_processing_handles_large_library(self, test_db):
        """Test that large libraries are processed in batches."""
        # Create library larger than batch size (100)
        num_videos = 250
        for i in range(num_videos):
            year = 1980 + (i % 40)  # Spread across 4 decades
            await test_db.create_video(
                title=f"Video {i}",
                artist="Test Artist",
                year=year,
                file_path=f"/test/video_{i}.mp4"
            )

        # Run apply sync
        job = Job(
            id="large-library-job",
            type=JobType.SYNC_DECADE_TAGS,
            status=JobStatus.RUNNING,
            metadata={
                "mode": "apply",
                "new_format": "{decade}s"
            }
        )

        await handle_sync_decade_tags(job)

        # Verify all videos processed
        assert job.status == JobStatus.COMPLETED
        assert job.result["videos_processed"] == num_videos
        assert job.result["tags_added"] == num_videos

        # Spot check some videos have correct tags
        videos = await test_db.list_videos(limit=10)
        for video in videos:
            tags = await test_db.get_video_tags(video["id"])
            assert len(tags) == 1
            assert tags[0]["source"] == "auto"
            # Tag name should match decade pattern
            assert tags[0]["name"].endswith("s")
