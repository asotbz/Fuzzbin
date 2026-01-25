"""Tests for the FFProbeClient class."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from fuzzbin.clients.ffprobe_client import FFProbeClient
from fuzzbin.common.config import FFProbeConfig
from fuzzbin.core.exceptions import (
    FFProbeExecutionError,
    FFProbeNotFoundError,
    FFProbeParseError,
)
from fuzzbin.parsers.ffprobe_models import FFProbeMediaInfo
from fuzzbin.parsers.ffprobe_parser import FFProbeParser


@pytest.fixture
def examples_dir():
    """Get path to examples directory."""
    return Path(__file__).parent.parent.parent / "examples"


@pytest.fixture
def ffprobe_sample_output(examples_dir):
    """Load ffprobe sample output."""
    with open(examples_dir / "ffprobe_sample_output.json") as f:
        return json.load(f)


@pytest.fixture
def ffprobe_config():
    """Create FFProbe configuration for testing.

    Note: FFProbeConfig only exposes ffprobe_path and timeout now.
    Other settings (show_format, show_streams) use defaults.
    """
    return FFProbeConfig(
        ffprobe_path="ffprobe",
        timeout=30,
    )


@pytest.fixture
def sample_video_file(tmp_path):
    """Create a temporary sample video file for testing."""
    video_file = tmp_path / "sample_video.mp4"
    video_file.write_bytes(b"fake video data")
    return video_file


class TestFFProbeClient:
    """Test suite for FFProbeClient."""

    @pytest.mark.asyncio
    async def test_from_config(self, ffprobe_config):
        """Test creating client from configuration."""
        client = FFProbeClient.from_config(config=ffprobe_config)
        assert client.ffprobe_path == "ffprobe"
        assert client.config.timeout == 30

    @pytest.mark.asyncio
    async def test_context_manager(self, ffprobe_config):
        """Test async context manager support."""
        async with FFProbeClient.from_config(ffprobe_config) as client:
            assert client is not None
            assert isinstance(client, FFProbeClient)

    @pytest.mark.asyncio
    async def test_binary_verification_not_found(self):
        """Test that missing ffprobe binary raises error."""
        config = FFProbeConfig(ffprobe_path="nonexistent_ffprobe_binary")
        client = FFProbeClient.from_config(config)

        with pytest.raises(FFProbeNotFoundError) as exc_info:
            await client._verify_binary()

        assert "not found" in str(exc_info.value).lower()
        assert exc_info.value.path == "nonexistent_ffprobe_binary"

    @pytest.mark.asyncio
    async def test_binary_verification_success(self, ffprobe_config):
        """Test successful binary verification."""
        # Mock shutil.which to return a path
        with patch("shutil.which", return_value="/usr/local/bin/ffprobe"):
            client = FFProbeClient.from_config(ffprobe_config)
            await client._verify_binary()
            assert client._verified is True

            # Verify it doesn't check again
            with patch("shutil.which", side_effect=Exception("Should not be called")):
                await client._verify_binary()

    @pytest.mark.asyncio
    async def test_get_media_info_success(
        self, ffprobe_config, sample_video_file, ffprobe_sample_output
    ):
        """Test successful media info extraction."""
        client = FFProbeClient.from_config(ffprobe_config)

        # Mock subprocess execution
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(
                json.dumps(ffprobe_sample_output).encode("utf-8"),
                b"",
            )
        )

        with patch("shutil.which", return_value="/usr/local/bin/ffprobe"):
            with patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
            ):
                media_info = await client.get_media_info(sample_video_file)

                assert isinstance(media_info, FFProbeMediaInfo)
                assert media_info.format.format_name == "mov,mp4,m4a,3gp,3g2,mj2"
                assert media_info.format.duration == 241.963

                video_stream = media_info.get_primary_video_stream()
                assert video_stream is not None
                assert video_stream.codec_name == "h264"
                assert video_stream.width == 1920
                assert video_stream.height == 1080

                audio_stream = media_info.get_primary_audio_stream()
                assert audio_stream is not None
                assert audio_stream.codec_name == "aac"
                assert audio_stream.channels == 2

    @pytest.mark.asyncio
    async def test_get_media_info_file_not_found(self, ffprobe_config):
        """Test error when video file doesn't exist."""
        client = FFProbeClient.from_config(ffprobe_config)
        nonexistent_file = Path("/tmp/nonexistent_video.mp4")

        with pytest.raises(FileNotFoundError):
            await client.get_media_info(nonexistent_file)

    @pytest.mark.asyncio
    async def test_execute_ffprobe_command_failure(self, ffprobe_config, sample_video_file):
        """Test handling of ffprobe command failure."""
        client = FFProbeClient.from_config(ffprobe_config)

        # Mock subprocess execution with error
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(
            return_value=(
                b"",
                b"Invalid file format",
            )
        )

        with patch("shutil.which", return_value="/usr/local/bin/ffprobe"):
            with patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
            ):
                with pytest.raises(FFProbeExecutionError) as exc_info:
                    await client.get_media_info(sample_video_file)

                assert exc_info.value.returncode == 1
                assert "Invalid file format" in exc_info.value.stderr

    @pytest.mark.asyncio
    async def test_execute_ffprobe_timeout(self, ffprobe_config, sample_video_file):
        """Test handling of ffprobe command timeout."""
        config = FFProbeConfig(timeout=5)
        client = FFProbeClient.from_config(config)

        # Mock subprocess that times out
        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch("shutil.which", return_value="/usr/local/bin/ffprobe"):
            with patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
            ):
                with pytest.raises(FFProbeExecutionError) as exc_info:
                    await client.get_media_info(sample_video_file)

                assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_parse_json_error(self, ffprobe_config, sample_video_file):
        """Test handling of JSON parsing errors."""
        client = FFProbeClient.from_config(ffprobe_config)

        # Mock subprocess execution with invalid JSON
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(
            return_value=(
                b"invalid json {not valid",
                b"",
            )
        )

        with patch("shutil.which", return_value="/usr/local/bin/ffprobe"):
            with patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_process,
            ):
                with pytest.raises(FFProbeParseError):
                    await client.get_media_info(sample_video_file)

    @pytest.mark.asyncio
    async def test_extract_video_metadata(self, ffprobe_sample_output):
        """Test extracting video metadata for database storage."""
        media_info = FFProbeParser.parse_media_info(ffprobe_sample_output)
        metadata = FFProbeParser.extract_video_metadata(media_info)

        # Verify all expected fields are present
        assert metadata["duration"] == 241.963
        assert metadata["width"] == 1920
        assert metadata["height"] == 1080
        assert metadata["video_codec"] == "h264"
        assert metadata["audio_codec"] == "aac"
        assert metadata["container_format"] == "mov,mp4,m4a,3gp,3g2,mj2"
        assert metadata["bitrate"] == 5120345
        assert metadata["file_size"] == 154891234
        assert metadata["audio_channels"] == 2
        assert metadata["audio_sample_rate"] == 48000
        assert metadata["aspect_ratio"] == "16:9"

        # Frame rate should be calculated from fraction
        assert metadata["frame_rate"] is not None
        assert 29.9 < metadata["frame_rate"] < 30.0

    @pytest.mark.asyncio
    async def test_frame_rate_conversion(self):
        """Test frame rate conversion from fraction strings."""
        from fuzzbin.parsers.ffprobe_models import FFProbeVideoStream

        # Test common frame rates
        stream_30 = FFProbeVideoStream(
            index=0,
            codec_name="h264",
            width=1920,
            height=1080,
            r_frame_rate="30/1",
        )
        assert stream_30.get_frame_rate_as_float() == 30.0

        stream_29_97 = FFProbeVideoStream(
            index=0,
            codec_name="h264",
            width=1920,
            height=1080,
            r_frame_rate="30000/1001",
        )
        frame_rate = stream_29_97.get_frame_rate_as_float()
        assert frame_rate is not None
        assert 29.96 < frame_rate < 29.98

        stream_24 = FFProbeVideoStream(
            index=0,
            codec_name="h264",
            width=1920,
            height=1080,
            r_frame_rate="24000/1001",
        )
        frame_rate_24 = stream_24.get_frame_rate_as_float()
        assert frame_rate_24 is not None
        assert 23.9 < frame_rate_24 < 24.0

    @pytest.mark.asyncio
    async def test_missing_streams(self):
        """Test handling of missing video/audio streams."""
        # Sample output with no streams
        empty_output = {
            "format": {
                "filename": "audio_only.m4a",
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "duration": "180.0",
                "size": "5000000",
                "bit_rate": "128000",
            },
            "streams": [],
        }

        media_info = FFProbeParser.parse_media_info(empty_output)
        metadata = FFProbeParser.extract_video_metadata(media_info)

        # Video fields should be None
        assert metadata["width"] is None
        assert metadata["height"] is None
        assert metadata["video_codec"] is None
        assert metadata["frame_rate"] is None

        # Audio fields should also be None
        assert metadata["audio_codec"] is None
        assert metadata["audio_channels"] is None

    @pytest.mark.asyncio
    async def test_sample_rate_conversion(self):
        """Test audio sample rate conversion to integer."""
        from fuzzbin.parsers.ffprobe_models import FFProbeAudioStream

        # Test with string sample rate
        stream = FFProbeAudioStream(
            index=1,
            codec_name="aac",
            sample_rate="48000",
            channels=2,
        )
        assert stream.get_sample_rate_as_int() == 48000

        # Test with integer sample rate (should be converted to string)
        stream2 = FFProbeAudioStream(
            index=1,
            codec_name="aac",
            sample_rate=44100,  # type: ignore
            channels=2,
        )
        assert stream2.sample_rate == "44100"
        assert stream2.get_sample_rate_as_int() == 44100
