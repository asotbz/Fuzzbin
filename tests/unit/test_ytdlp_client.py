"""Tests for YTDLPClient."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fuzzbin.clients.ytdlp_client import YTDLPClient
from fuzzbin.common.config import YTDLPConfig
from fuzzbin.core.exceptions import (
    InvalidPathError,
    YTDLPExecutionError,
    YTDLPNotFoundError,
    YTDLPParseError,
)
from fuzzbin.parsers.ytdlp_models import DownloadProgress, YTDLPDownloadResult, YTDLPSearchResult


@pytest.fixture
def ytdlp_config():
    """Create yt-dlp configuration for testing."""
    return YTDLPConfig(
        ytdlp_path="yt-dlp",
        search_max_results=5,
        geo_bypass=False,
        quiet=True,
        timeout=300,
    )


@pytest.fixture
def mock_search_output():
    """Create mock yt-dlp search output (newline-delimited JSON)."""
    data = {
        "id": "5WPbqYoz9HA",
        "title": "Bush - Machinehead",
        "webpage_url": "https://www.youtube.com/watch?v=5WPbqYoz9HA",
        "channel": "Bush",
        "channel_follower_count": 411000,
        "view_count": 28794614,
        "duration": 257,
    }
    return json.dumps(data) + "\n"


class TestYTDLPClient:
    """Test suite for YTDLPClient."""

    @pytest.mark.asyncio
    async def test_from_config(self, ytdlp_config):
        """Test creating client from configuration."""
        async with YTDLPClient.from_config(ytdlp_config) as client:
            assert client.ytdlp_path == "yt-dlp"
            assert client.config.search_max_results == 5
            assert client.config.quiet is True

    @pytest.mark.asyncio
    async def test_context_manager(self, ytdlp_config):
        """Test async context manager protocol."""
        async with YTDLPClient.from_config(ytdlp_config) as client:
            assert isinstance(client, YTDLPClient)

    @pytest.mark.asyncio
    async def test_search_success(self, ytdlp_config, mock_search_output):
        """Test successful search."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock successful subprocess execution
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                mock_search_output.encode(),
                b"",
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            async with YTDLPClient.from_config(ytdlp_config) as client:
                results = await client.search("Bush", "Machinehead", max_results=5)

                assert len(results) == 1
                assert isinstance(results[0], YTDLPSearchResult)
                assert results[0].title == "Bush - Machinehead"
                assert results[0].channel == "Bush"
                assert results[0].view_count == 28794614
                assert results[0].channel_follower_count == 411000
                assert results[0].duration == 257

            # Verify correct command was called
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0]
            assert call_args[0] == "yt-dlp"
            assert "--dump-json" in call_args
            assert "--flat-playlist" in call_args
            assert "ytsearch5:Bush Machinehead" in call_args

    @pytest.mark.asyncio
    async def test_search_multiple_results(self, ytdlp_config):
        """Test search with multiple results."""
        # Create newline-delimited JSON with 3 results
        output_lines = []
        for i in range(3):
            data = {
                "id": f"test_id_{i}",
                "title": f"Test Video {i}",
                "webpage_url": f"https://www.youtube.com/watch?v=test_id_{i}",
                "channel": f"Channel {i}",
                "view_count": 1000 * (i + 1),
            }
            output_lines.append(json.dumps(data))
        mock_output = "\n".join(output_lines) + "\n"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                mock_output.encode(),
                b"",
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            async with YTDLPClient.from_config(ytdlp_config) as client:
                results = await client.search("Artist", "Track", max_results=3)

                assert len(results) == 3
                assert results[0].title == "Test Video 0"
                assert results[1].title == "Test Video 1"
                assert results[2].title == "Test Video 2"

    @pytest.mark.asyncio
    async def test_search_ytdlp_not_found(self, ytdlp_config):
        """Test search when yt-dlp binary not found."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = FileNotFoundError()

            async with YTDLPClient.from_config(ytdlp_config) as client:
                with pytest.raises(YTDLPNotFoundError) as exc_info:
                    await client.search("Artist", "Title")

                assert "yt-dlp binary not found" in str(exc_info.value)
                assert "pip install yt-dlp" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_command_fails(self, ytdlp_config):
        """Test search when yt-dlp command fails."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                b"",
                b"ERROR: Video not available",
            )
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            async with YTDLPClient.from_config(ytdlp_config) as client:
                with pytest.raises(YTDLPExecutionError) as exc_info:
                    await client.search("Artist", "Title")

                assert exc_info.value.returncode == 1
                assert "Video not available" in exc_info.value.stderr

    @pytest.mark.asyncio
    async def test_search_timeout(self, ytdlp_config):
        """Test search timeout handling."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            # Make communicate hang forever using an async function that never completes
            async def never_completes():
                await asyncio.sleep(999)  # Sleep for a very long time
                return (b"", b"")

            mock_process.communicate = never_completes
            mock_exec.return_value = mock_process

            # Use very short timeout
            ytdlp_config.timeout = 0.1

            async with YTDLPClient.from_config(ytdlp_config) as client:
                with pytest.raises(YTDLPExecutionError) as exc_info:
                    await client.search("Artist", "Title")

                assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_search_malformed_json(self, ytdlp_config):
        """Test search with malformed JSON (should skip bad lines)."""
        # Mix of valid and invalid JSON lines
        mock_output = """{"id": "1", "title": "Good Video", "webpage_url": "https://youtube.com/watch?v=1"}
{invalid json here}
{"id": "2", "title": "Another Good Video", "webpage_url": "https://youtube.com/watch?v=2"}
"""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                mock_output.encode(),
                b"",
            )
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            async with YTDLPClient.from_config(ytdlp_config) as client:
                results = await client.search("Artist", "Track")

                # Should only return the 2 valid entries
                assert len(results) == 2
                assert results[0].id == "1"
                assert results[1].id == "2"

    @pytest.mark.asyncio
    async def test_download_success(self, ytdlp_config, tmp_path):
        """Test successful download."""
        output_file = tmp_path / "video.mp4"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            # Create mock downloaded file
            output_file.write_bytes(b"fake video content here")

            async with YTDLPClient.from_config(ytdlp_config) as client:
                result = await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                )

                assert isinstance(result, YTDLPDownloadResult)
                assert result.output_path == output_file
                assert result.file_size == 23  # len("fake video content here")
                assert result.url == "https://www.youtube.com/watch?v=test"

            # Verify correct command was called
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0]
            assert call_args[0] == "yt-dlp"
            assert "--format" in call_args
            assert "--output" in call_args
            assert str(output_file) in call_args
            assert "--no-playlist" in call_args
            assert "https://www.youtube.com/watch?v=test" in call_args

    @pytest.mark.asyncio
    async def test_download_with_custom_format(self, ytdlp_config, tmp_path):
        """Test download with custom format specification."""
        output_file = tmp_path / "video.mp4"
        custom_format = "best[height<=720]"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            output_file.write_bytes(b"video")

            async with YTDLPClient.from_config(ytdlp_config) as client:
                result = await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                    format_spec=custom_format,
                )

                assert result.output_path == output_file

            # Verify custom format was used
            call_args = mock_exec.call_args[0]
            format_idx = call_args.index("--format")
            assert call_args[format_idx + 1] == custom_format

    @pytest.mark.asyncio
    async def test_download_invalid_path(self, ytdlp_config):
        """Test download with invalid output path."""
        invalid_path = Path("/nonexistent/directory/video.mp4")

        async with YTDLPClient.from_config(ytdlp_config) as client:
            with pytest.raises(InvalidPathError) as exc_info:
                await client.download(
                    "https://www.youtube.com/watch?v=test",
                    invalid_path,
                )

            assert exc_info.value.path == invalid_path.parent
            assert "does not exist" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_command_fails(self, ytdlp_config, tmp_path):
        """Test download when yt-dlp command fails."""
        output_file = tmp_path / "video.mp4"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (
                b"",
                b"ERROR: Unable to download video",
            )
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            async with YTDLPClient.from_config(ytdlp_config) as client:
                with pytest.raises(YTDLPExecutionError) as exc_info:
                    await client.download(
                        "https://www.youtube.com/watch?v=test",
                        output_file,
                    )

                assert exc_info.value.returncode == 1
                assert "Unable to download video" in exc_info.value.stderr

    @pytest.mark.asyncio
    async def test_download_file_not_created(self, ytdlp_config, tmp_path):
        """Test download when command succeeds but file not created."""
        output_file = tmp_path / "video.mp4"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            # Don't create the file

            async with YTDLPClient.from_config(ytdlp_config) as client:
                with pytest.raises(YTDLPExecutionError) as exc_info:
                    await client.download(
                        "https://www.youtube.com/watch?v=test",
                        output_file,
                    )

                assert "file not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_with_geo_bypass(self, tmp_path):
        """Test download with geo bypass enabled."""
        config = YTDLPConfig(geo_bypass=True)
        output_file = tmp_path / "video.mp4"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            output_file.write_bytes(b"video")

            async with YTDLPClient.from_config(config) as client:
                await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                )

            # Verify --geo-bypass was included
            call_args = mock_exec.call_args[0]
            assert "--geo-bypass" in call_args

    @pytest.mark.asyncio
    async def test_download_quiet_mode(self, tmp_path):
        """Test download with quiet mode enabled."""
        config = YTDLPConfig(quiet=True)
        output_file = tmp_path / "video.mp4"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            output_file.write_bytes(b"video")

            async with YTDLPClient.from_config(config) as client:
                await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                )

            # Verify --quiet was included (not --progress)
            call_args = mock_exec.call_args[0]
            assert "--quiet" in call_args
            assert "--progress" not in call_args

    @pytest.mark.asyncio
    async def test_parse_progress_line(self, ytdlp_config):
        """Test progress line parsing."""
        async with YTDLPClient.from_config(ytdlp_config) as client:
            # Test typical progress line
            line = "[download]  45.2% of 10.5MiB at 1.2MiB/s ETA 00:04"
            progress = client._parse_progress_line(line)

            assert progress is not None
            assert progress.percent == 45.2
            assert progress.total_bytes == 11010048  # 10.5 MiB
            assert progress.downloaded_bytes == int(11010048 * 0.452)
            assert abs(progress.speed_bytes_per_sec - 1258291.2) < 1  # 1.2 MiB/s (allow rounding)
            assert progress.eta_seconds == 4
            assert progress.status == "downloading"

    @pytest.mark.asyncio
    async def test_parse_progress_line_100_percent(self, ytdlp_config):
        """Test progress line at 100%."""
        async with YTDLPClient.from_config(ytdlp_config) as client:
            line = "[download] 100% of 10.5MiB in 00:08"
            progress = client._parse_progress_line(line)

            assert progress is not None
            assert progress.percent == 100.0
            assert progress.status == "finished"

    @pytest.mark.asyncio
    async def test_parse_size(self, ytdlp_config):
        """Test size parsing."""
        async with YTDLPClient.from_config(ytdlp_config) as client:
            assert client._parse_size("10.5MiB") == 11010048
            assert client._parse_size("1.2GiB") == 1288490188
            assert client._parse_size("500KiB") == 512000
            assert client._parse_size("1MB") == 1000000
            assert client._parse_size("invalid") is None

    @pytest.mark.asyncio
    async def test_parse_speed(self, ytdlp_config):
        """Test speed parsing."""
        async with YTDLPClient.from_config(ytdlp_config) as client:
            assert abs(client._parse_speed("1.2MiB/s") - 1258291.2) < 1
            assert client._parse_speed("500KiB/s") == 512000.0
            assert client._parse_speed("invalid") is None

    @pytest.mark.asyncio
    async def test_parse_eta(self, ytdlp_config):
        """Test ETA parsing."""
        async with YTDLPClient.from_config(ytdlp_config) as client:
            assert client._parse_eta("00:04") == 4
            assert client._parse_eta("01:23") == 83
            assert client._parse_eta("Unknown ETA") is None

    @pytest.mark.asyncio
    async def test_download_with_progress(self, ytdlp_config, tmp_path):
        """Test download with progress callback."""
        output_file = tmp_path / "video.mp4"
        progress_updates = []

        def on_progress(progress: DownloadProgress):
            progress_updates.append(progress)

        # Mock progress output
        mock_output = b"""[download] Destination: /path/to/video.mp4
[download]  25.0% of 10.0MiB at 1.0MiB/s ETA 00:08
[download]  50.0% of 10.0MiB at 1.5MiB/s ETA 00:03
[download]  75.0% of 10.0MiB at 2.0MiB/s ETA 00:01
[download] 100% of 10.0MiB in 00:05
"""

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()

            # Mock stdout as async iterator
            async def mock_stdout():
                for line in mock_output.split(b"\n"):
                    yield line

            mock_process.stdout = mock_stdout()
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            # Create output file
            output_file.write_bytes(b"fake video")

            async with YTDLPClient.from_config(ytdlp_config) as client:
                result = await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                    progress_callback=on_progress,
                )

                assert result.output_path == output_file

            # Verify progress updates were received
            assert len(progress_updates) >= 3
            assert any(p.percent == 25.0 for p in progress_updates)
            assert any(p.percent == 50.0 for p in progress_updates)
            assert any(p.percent == 100.0 for p in progress_updates)

            # Verify --newline was included in command
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0]
            assert "--newline" in call_args

    @pytest.mark.asyncio
    async def test_download_without_progress(self, ytdlp_config, tmp_path):
        """Test download without progress callback uses old path."""
        output_file = tmp_path / "video.mp4"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            output_file.write_bytes(b"video")

            async with YTDLPClient.from_config(ytdlp_config) as client:
                result = await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                    # No progress_callback
                )

                assert result.output_path == output_file

            # Verify --newline was NOT included (uses old path)
            call_args = mock_exec.call_args[0]
            assert "--newline" not in call_args


@pytest.mark.asyncio
class TestAsyncCallbacks:
    """Test async callback support."""

    async def test_async_progress_callback(self, ytdlp_config, tmp_path):
        """Test async progress callback."""
        output_file = tmp_path / "video.mp4"
        progress_updates = []

        async def async_callback(progress):
            await asyncio.sleep(0.001)  # Simulate async work
            progress_updates.append(progress.percent)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.__aiter__.return_value = iter(
                [
                    b"[download] 25.0% of 10.00MiB at 1.00MiB/s ETA 00:08\n",
                    b"[download] 50.0% of 10.00MiB at 1.00MiB/s ETA 00:05\n",
                    b"[download] 100% of 10.00MiB at 1.00MiB/s ETA 00:00\n",
                    b"[download] 100% of 10.00MiB in 00:10\n",
                ]
            )
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            output_file.write_bytes(b"video")

            async with YTDLPClient.from_config(ytdlp_config) as client:
                result = await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                    progress_callback=async_callback,
                )

                assert result.output_path == output_file
                assert len(progress_updates) >= 3  # At least 25%, 50%, 100%
                assert 100.0 in progress_updates


@pytest.mark.asyncio
class TestHooksAPI:
    """Test hooks API for download lifecycle."""

    async def test_sync_hooks(self, ytdlp_config, tmp_path):
        """Test synchronous hooks are called correctly."""
        output_file = tmp_path / "video.mp4"
        hook_calls = []

        def on_start():
            hook_calls.append("start")

        def on_progress(progress):
            hook_calls.append(f"progress:{progress.percent}")

        def on_complete(result):
            hook_calls.append(f"complete:{result.file_size}")

        from fuzzbin.parsers.ytdlp_models import DownloadHooks

        hooks = DownloadHooks(
            on_start=on_start,
            on_progress=on_progress,
            on_complete=on_complete,
        )

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.__aiter__.return_value = iter(
                [
                    b"[download] 50.0% of 10.00MiB at 1.00MiB/s ETA 00:05\n",
                    b"[download] 100% of 10.00MiB in 00:10\n",
                ]
            )
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            output_file.write_bytes(b"test video content")

            async with YTDLPClient.from_config(ytdlp_config) as client:
                result = await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                    hooks=hooks,
                )

                assert result.output_path == output_file
                assert "start" in hook_calls
                assert any("progress" in call for call in hook_calls)
                assert any("complete" in call for call in hook_calls)

    async def test_async_hooks(self, ytdlp_config, tmp_path):
        """Test async hooks are awaited correctly."""
        output_file = tmp_path / "video.mp4"
        hook_calls = []

        async def on_start():
            await asyncio.sleep(0.001)
            hook_calls.append("async_start")

        async def on_progress(progress):
            await asyncio.sleep(0.001)
            hook_calls.append(f"async_progress:{progress.percent}")

        async def on_complete(result):
            await asyncio.sleep(0.001)
            hook_calls.append(f"async_complete:{result.file_size}")

        from fuzzbin.parsers.ytdlp_models import DownloadHooks

        hooks = DownloadHooks(
            on_start=on_start,
            on_progress=on_progress,
            on_complete=on_complete,
        )

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.__aiter__.return_value = iter(
                [
                    b"[download] 100% of 10.00MiB in 00:10\n",
                ]
            )
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            output_file.write_bytes(b"test video")

            async with YTDLPClient.from_config(ytdlp_config) as client:
                result = await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                    hooks=hooks,
                )

                assert result.output_path == output_file
                assert "async_start" in hook_calls
                assert any("async_progress" in call for call in hook_calls)
                assert any("async_complete" in call for call in hook_calls)

    async def test_on_error_hook(self, ytdlp_config, tmp_path):
        """Test on_error hook is called on download failure."""
        output_file = tmp_path / "video.mp4"
        error_caught = []

        async def on_error(error):
            error_caught.append(str(error))

        from fuzzbin.parsers.ytdlp_models import DownloadHooks

        hooks = DownloadHooks(on_error=on_error)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.__aiter__.return_value = iter([])
            mock_process.stderr = AsyncMock()
            mock_process.stderr.read = AsyncMock(return_value=b"Error message")
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 1  # Failure
            mock_exec.return_value = mock_process

            async with YTDLPClient.from_config(ytdlp_config) as client:
                with pytest.raises(YTDLPExecutionError):
                    await client.download(
                        "https://www.youtube.com/watch?v=test",
                        output_file,
                        hooks=hooks,
                    )

                # on_error should have been called
                assert len(error_caught) == 1
                assert "yt-dlp failed" in error_caught[0]

    async def test_mixed_sync_async_hooks(self, ytdlp_config, tmp_path):
        """Test mix of sync and async hooks."""
        output_file = tmp_path / "video.mp4"
        hook_calls = []

        def sync_on_start():
            hook_calls.append("sync_start")

        async def async_on_progress(progress):
            await asyncio.sleep(0.001)
            hook_calls.append("async_progress")

        from fuzzbin.parsers.ytdlp_models import DownloadHooks

        hooks = DownloadHooks(
            on_start=sync_on_start,
            on_progress=async_on_progress,
        )

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.__aiter__.return_value = iter(
                [b"[download] 100% of 10.00MiB in 00:10\n"]
            )
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            output_file.write_bytes(b"video")

            async with YTDLPClient.from_config(ytdlp_config) as client:
                await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                    hooks=hooks,
                )

                assert "sync_start" in hook_calls
                assert "async_progress" in hook_calls


@pytest.mark.asyncio
class TestCancellation:
    """Test download cancellation."""

    async def test_cancellation_token_basic(self):
        """Test CancellationToken basic functionality."""
        from fuzzbin.parsers.ytdlp_models import CancellationToken

        token = CancellationToken()
        assert not token.is_cancelled()

        token.cancel()
        assert token.is_cancelled()

        token.reset()
        assert not token.is_cancelled()

    async def test_download_cancellation(self, ytdlp_config, tmp_path):
        """Test download can be cancelled mid-progress."""
        output_file = tmp_path / "video.mp4"
        from fuzzbin.parsers.ytdlp_models import CancellationToken, DownloadHooks
        from fuzzbin.core.exceptions import DownloadCancelledError

        token = CancellationToken()
        progress_count = [0]

        def on_progress(progress):
            progress_count[0] += 1
            if progress.percent >= 50.0:
                token.cancel()

        hooks = DownloadHooks(on_progress=on_progress)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.__aiter__.return_value = iter(
                [
                    b"[download] 25.0% of 10.00MiB at 1.00MiB/s ETA 00:08\n",
                    b"[download] 50.0% of 10.00MiB at 1.00MiB/s ETA 00:05\n",
                    b"[download] 75.0% of 10.00MiB at 1.00MiB/s ETA 00:02\n",
                    b"[download] 100% of 10.00MiB in 00:10\n",
                ]
            )
            mock_process.kill = MagicMock()
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            async with YTDLPClient.from_config(ytdlp_config) as client:
                with pytest.raises(DownloadCancelledError) as exc_info:
                    await client.download(
                        "https://www.youtube.com/watch?v=test",
                        output_file,
                        hooks=hooks,
                        cancellation_token=token,
                    )

                assert "cancelled" in str(exc_info.value).lower()
                # Verify process.kill() was called
                mock_process.kill.assert_called_once()

    async def test_cancellation_without_hooks(self, ytdlp_config, tmp_path):
        """Test cancellation with CancellationToken but no hooks."""
        output_file = tmp_path / "video.mp4"
        from fuzzbin.parsers.ytdlp_models import CancellationToken
        from fuzzbin.core.exceptions import DownloadCancelledError

        token = CancellationToken()

        # Cancel immediately
        token.cancel()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.__aiter__.return_value = iter([])
            mock_process.kill = MagicMock()
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            async with YTDLPClient.from_config(ytdlp_config) as client:
                with pytest.raises(DownloadCancelledError):
                    await client.download(
                        "https://www.youtube.com/watch?v=test",
                        output_file,
                        cancellation_token=token,
                    )

    async def test_backward_compat_progress_callback_with_hooks(
        self, ytdlp_config, tmp_path
    ):
        """Test progress_callback is merged with hooks correctly."""
        output_file = tmp_path / "video.mp4"
        from fuzzbin.parsers.ytdlp_models import DownloadHooks

        progress_calls = []
        start_calls = []

        def progress_callback(progress):
            progress_calls.append(progress.percent)

        def on_start():
            start_calls.append(True)

        hooks = DownloadHooks(on_start=on_start)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.stdout = AsyncMock()
            mock_process.stdout.__aiter__.return_value = iter(
                [b"[download] 100% of 10.00MiB in 00:10\n"]
            )
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            output_file.write_bytes(b"video")

            async with YTDLPClient.from_config(ytdlp_config) as client:
                await client.download(
                    "https://www.youtube.com/watch?v=test",
                    output_file,
                    progress_callback=progress_callback,
                    hooks=hooks,
                )

                # Both should be called
                assert len(start_calls) > 0
                assert len(progress_calls) > 0
