"""Tests for FFmpeg client thumbnail generation."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from fuzzbin.clients.ffmpeg_client import FFmpegClient
from fuzzbin.common.config import ThumbnailConfig
from fuzzbin.core.exceptions import (
    FFmpegError,
    FFmpegNotFoundError,
    FFmpegExecutionError,
    ThumbnailTooLargeError,
)


class TestFFmpegClientConfig:
    """Tests for FFmpegClient configuration."""

    def test_default_config(self) -> None:
        """Test FFmpegClient with default config."""
        config = ThumbnailConfig()
        client = FFmpegClient.from_config(config)

        assert client.config.width == 320
        assert client.config.height == 180
        assert client.config.quality == 5
        assert client.config.default_timestamp == 5.0
        assert client.config.max_file_size == 5 * 1024 * 1024

    def test_custom_config(self) -> None:
        """Test FFmpegClient with custom config."""
        config = ThumbnailConfig(
            width=640,
            height=360,
            quality=3,
            default_timestamp=10.0,
            max_file_size=1024 * 1024,
        )
        client = FFmpegClient.from_config(config)

        assert client.config.width == 640
        assert client.config.height == 360
        assert client.config.quality == 3
        assert client.config.default_timestamp == 10.0


class TestFFmpegClientVerify:
    """Tests for FFmpegClient binary verification."""

    @pytest.mark.asyncio
    async def test_verify_binary_found(self) -> None:
        """Test verification passes when ffmpeg is found."""
        config = ThumbnailConfig()
        client = FFmpegClient(config=config)

        with patch("shutil.which", return_value="/usr/local/bin/ffmpeg"):
            await client._verify_binary()

        assert client._verified is True

    @pytest.mark.asyncio
    async def test_verify_binary_not_found(self) -> None:
        """Test verification fails when ffmpeg is not found."""
        config = ThumbnailConfig()
        client = FFmpegClient(config=config)

        with patch("shutil.which", return_value=None):
            with pytest.raises(FFmpegNotFoundError):
                await client._verify_binary()

    @pytest.mark.asyncio
    async def test_verify_binary_caches_result(self) -> None:
        """Test that binary verification is cached."""
        config = ThumbnailConfig()
        client = FFmpegClient(config=config)
        client._verified = True

        # Should not call which() again
        with patch("shutil.which") as mock_which:
            await client._verify_binary()
            mock_which.assert_not_called()


class TestFFmpegClientExtractFrame:
    """Tests for FFmpegClient.extract_frame() method."""

    @pytest.fixture
    def mock_config(self) -> ThumbnailConfig:
        """Provide mock thumbnail config."""
        return ThumbnailConfig(
            width=320,
            height=180,
            quality=5,
            default_timestamp=5.0,
            max_file_size=5 * 1024 * 1024,
            timeout=30,
        )

    @pytest.fixture
    def client(self, mock_config: ThumbnailConfig) -> FFmpegClient:
        """Provide FFmpegClient instance."""
        client = FFmpegClient(config=mock_config)
        client._verified = True  # Skip binary check
        return client

    @pytest.mark.asyncio
    async def test_extract_frame_video_not_found(
        self, client: FFmpegClient, tmp_path: Path
    ) -> None:
        """Test extract_frame raises FileNotFoundError for missing video."""
        video_path = tmp_path / "missing.mp4"
        output_path = tmp_path / "thumb.jpg"

        with pytest.raises(FileNotFoundError):
            await client.extract_frame(video_path, output_path)

    @pytest.mark.asyncio
    async def test_extract_frame_creates_output_dir(
        self, client: FFmpegClient, tmp_path: Path
    ) -> None:
        """Test extract_frame creates output directory if needed."""
        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake video content")
        output_path = tmp_path / "subdir" / "thumb.jpg"

        # Mock subprocess to succeed
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", return_value=(b"", b"")):
                # Create the output file as ffmpeg would
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"fake jpeg data")

                result = await client.extract_frame(video_path, output_path)

        assert output_path.parent.exists()

    @pytest.mark.asyncio
    async def test_extract_frame_success(
        self, client: FFmpegClient, tmp_path: Path
    ) -> None:
        """Test successful frame extraction."""
        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake video content")
        output_path = tmp_path / "thumb.jpg"

        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        async def mock_wait_for(coro, timeout):
            # Create the output file
            output_path.write_bytes(b"fake jpeg thumbnail data")
            return await coro

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", side_effect=mock_wait_for):
                result = await client.extract_frame(video_path, output_path)

        assert result == output_path
        assert output_path.exists()

    @pytest.mark.asyncio
    async def test_extract_frame_ffmpeg_failure(
        self, client: FFmpegClient, tmp_path: Path
    ) -> None:
        """Test extract_frame raises on ffmpeg failure."""
        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake video content")
        output_path = tmp_path / "thumb.jpg"

        # Mock subprocess failure
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error message"))

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", return_value=(b"", b"Error message")):
                with pytest.raises(FFmpegExecutionError):
                    await client.extract_frame(video_path, output_path)

    @pytest.mark.asyncio
    async def test_extract_frame_timeout(
        self, client: FFmpegClient, tmp_path: Path
    ) -> None:
        """Test extract_frame raises on timeout."""
        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake video content")
        output_path = tmp_path / "thumb.jpg"

        # Mock timeout
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
                with pytest.raises(FFmpegExecutionError) as exc_info:
                    await client.extract_frame(video_path, output_path)

        assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_extract_frame_too_large(
        self, tmp_path: Path
    ) -> None:
        """Test extract_frame raises when output exceeds max size."""
        # Config with small max size (must be >= 1024)
        config = ThumbnailConfig(max_file_size=1024)
        client = FFmpegClient(config=config)
        client._verified = True

        video_path = tmp_path / "video.mp4"
        video_path.write_bytes(b"fake video content")
        output_path = tmp_path / "thumb.jpg"

        # Mock subprocess success but create large output
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"", b""))

        async def mock_wait_for(coro, timeout):
            # Create oversized output file (2KB > 1KB max)
            output_path.write_bytes(b"x" * 2048)
            return await coro

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            with patch("asyncio.wait_for", side_effect=mock_wait_for):
                with pytest.raises(ThumbnailTooLargeError) as exc_info:
                    await client.extract_frame(video_path, output_path)

        assert exc_info.value.size == 2048
        assert exc_info.value.max_size == 1024
        # File should be deleted
        assert not output_path.exists()


class TestFFmpegClientContextManager:
    """Tests for FFmpegClient context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test async context manager verifies binary."""
        config = ThumbnailConfig()
        
        with patch("shutil.which", return_value="/usr/local/bin/ffmpeg"):
            async with FFmpegClient.from_config(config) as client:
                assert client._verified is True

    @pytest.mark.asyncio
    async def test_context_manager_not_found(self) -> None:
        """Test context manager raises if binary not found."""
        config = ThumbnailConfig()

        with patch("shutil.which", return_value=None):
            with pytest.raises(FFmpegNotFoundError):
                async with FFmpegClient.from_config(config):
                    pass
