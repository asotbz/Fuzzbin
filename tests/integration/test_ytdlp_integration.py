"""Integration tests for YTDLPClient (requires yt-dlp installed)."""

from pathlib import Path

import pytest

from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.common.config import YTDLPConfig
from fuzzbin.parsers.ytdlp_models import YTDLPDownloadResult, YTDLPSearchResult


@pytest.mark.slow
@pytest.mark.integration
class TestYTDLPIntegration:
    """Integration tests that execute real yt-dlp commands."""

    @pytest.mark.asyncio
    async def test_search_real(self):
        """Test real YouTube search."""
        config = YTDLPConfig(search_max_results=3)

        async with YTDLPClient.from_config(config) as client:
            results = await client.search("Bush", "Machinehead", max_results=3)

            # Verify we got results
            assert len(results) > 0
            assert len(results) <= 3

            # Verify all results have required fields
            for result in results:
                assert isinstance(result, YTDLPSearchResult)
                assert result.id
                assert result.title
                assert result.url
                assert "youtube.com" in result.url

            # First result should be relevant
            first_result = results[0]
            assert first_result.title is not None
            assert len(first_result.title) > 0

    @pytest.mark.asyncio
    async def test_search_multiple_artists(self):
        """Test search with different artists."""
        config = YTDLPConfig(search_max_results=2)

        test_cases = [
            ("Robin Thicke", "Blurred Lines"),
            ("Bush", "Machinehead"),
        ]

        async with YTDLPClient.from_config(config) as client:
            for artist, track in test_cases:
                results = await client.search(artist, track, max_results=2)

                assert len(results) > 0
                assert all(r.title for r in results)
                assert all(r.url for r in results)

    @pytest.mark.asyncio
    async def test_download_real(self, tmp_path):
        """
        Test real video download (short test video).

        Note: This downloads "Me at the zoo" - the first YouTube video (18 seconds).
        """
        config = YTDLPConfig(quiet=True)
        output_file = tmp_path / "test_video.mp4"

        # Use the first YouTube video ever uploaded (short, public domain-ish)
        test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"  # Me at the zoo

        async with YTDLPClient.from_config(config) as client:
            result = await client.download(test_url, output_file)

            # Verify download completed
            assert isinstance(result, YTDLPDownloadResult)
            assert output_file.exists()
            assert result.file_size > 0
            assert result.output_path == output_file
            assert result.url == test_url

            # Verify file is actually an MP4
            # MP4 files start with ftyp signature
            with open(output_file, "rb") as f:
                f.seek(4)
                file_type = f.read(4)
                assert file_type == b"ftyp"  # MP4 signature

    @pytest.mark.asyncio
    async def test_search_then_download(self, tmp_path):
        """Test complete workflow: search then download."""
        config = YTDLPConfig(search_max_results=1, quiet=True)
        output_file = tmp_path / "downloaded_video.mp4"

        async with YTDLPClient.from_config(config) as client:
            # Search for a specific short video
            results = await client.search("jawed", "me at the zoo", max_results=1)

            assert len(results) > 0
            video = results[0]

            # Download the first result
            result = await client.download(video.url, output_file)

            assert output_file.exists()
            assert result.file_size > 0
