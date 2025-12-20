"""ffprobe CLI client for video file metadata extraction."""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from ..common.config import FFProbeConfig
from ..core.exceptions import (
    FFProbeError,
    FFProbeExecutionError,
    FFProbeNotFoundError,
    FFProbeParseError,
)
from ..parsers.ffprobe_models import FFProbeMediaInfo
from ..parsers.ffprobe_parser import FFProbeParser

logger = structlog.get_logger(__name__)


class FFProbeClient:
    """
    Async client for ffprobe CLI tool.

    Provides video file metadata extraction functionality with fully async
    subprocess execution. Extracts codec information, resolution, duration,
    bitrate, and other technical details from video files.

    **Requirements:**
        The ffprobe binary must be installed separately and available in PATH.
        Install via: `brew install ffmpeg` (includes ffprobe) or download from ffmpeg.org

    Features:
    - Extract complete media information (format, video streams, audio streams)
    - Parse codec, resolution, duration, bitrate, frame rate
    - Support for multiple video/audio streams
    - Non-blocking async subprocess execution
    - Configurable timeout
    - Structured logging with operation context

    Example:
        >>> import asyncio
        >>> from pathlib import Path
        >>> from fuzzbin.clients.ffprobe_client import FFProbeClient
        >>> from fuzzbin.common.config import FFProbeConfig
        >>>
        >>> async def main():
        ...     config = FFProbeConfig(timeout=30)
        ...
        ...     async with FFProbeClient.from_config(config) as client:
        ...         # Get media info
        ...         video_path = Path("downloads/video.mp4")
        ...         media_info = await client.get_media_info(video_path)
        ...
        ...         # Access parsed data
        ...         print(f"Duration: {media_info.format.duration}s")
        ...         video_stream = media_info.get_primary_video_stream()
        ...         if video_stream:
        ...             print(f"Resolution: {video_stream.width}x{video_stream.height}")
        ...             print(f"Codec: {video_stream.codec_name}")
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        config: Optional[FFProbeConfig] = None,
        ffprobe_path: str = "ffprobe",
    ):
        """
        Initialize the ffprobe client.

        Args:
            config: FFProbeConfig instance for client configuration
            ffprobe_path: Path to ffprobe binary (default: "ffprobe" from PATH)
        """
        self.config = config or FFProbeConfig()
        self.ffprobe_path = ffprobe_path
        self.logger = structlog.get_logger(__name__)
        self._verified = False

    async def __aenter__(self) -> "FFProbeClient":
        """Async context manager entry."""
        await self._verify_binary()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        pass

    @classmethod
    def from_config(cls, config: FFProbeConfig) -> "FFProbeClient":
        """
        Create FFProbeClient from FFProbeConfig.

        Args:
            config: FFProbeConfig instance

        Returns:
            FFProbeClient instance configured from config

        Example:
            >>> from fuzzbin.common.config import FFProbeConfig
            >>> config = FFProbeConfig(timeout=60)
            >>> async with FFProbeClient.from_config(config) as client:
            ...     media_info = await client.get_media_info(Path("video.mp4"))
        """
        return cls(config=config, ffprobe_path=config.ffprobe_path)

    async def _verify_binary(self) -> None:
        """
        Verify that ffprobe binary exists and is executable.

        Raises:
            FFProbeNotFoundError: If ffprobe binary not found in PATH
        """
        if self._verified:
            return

        # Check if binary exists in PATH
        if not shutil.which(self.ffprobe_path):
            raise FFProbeNotFoundError(
                f"ffprobe binary not found at '{self.ffprobe_path}'. "
                "Please install ffmpeg: brew install ffmpeg (includes ffprobe)",
                path=self.ffprobe_path,
            )

        self.logger.debug(
            "ffprobe_binary_verified",
            path=self.ffprobe_path,
        )
        self._verified = True

    async def _execute_ffprobe(
        self,
        args: List[str],
        parse_json: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute ffprobe command asynchronously.

        Uses asyncio.create_subprocess_exec() for non-blocking subprocess execution.
        Handles command errors, timeouts, and JSON parsing.

        Args:
            args: Command line arguments for ffprobe
            parse_json: If True, parse stdout as JSON (default: True)

        Returns:
            Parsed JSON dictionary from ffprobe output

        Raises:
            FFProbeNotFoundError: If ffprobe binary not found
            FFProbeExecutionError: If command fails or times out
            FFProbeParseError: If JSON parsing fails
        """
        await self._verify_binary()

        cmd = [self.ffprobe_path] + args

        self.logger.debug(
            "ffprobe_execute",
            command=" ".join(cmd),
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.timeout,
            )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                self.logger.error(
                    "ffprobe_failed",
                    returncode=process.returncode,
                    stderr=error_msg[:500],  # Truncate long errors
                )
                raise FFProbeExecutionError(
                    f"ffprobe failed with exit code {process.returncode}",
                    returncode=process.returncode,
                    stderr=error_msg,
                )

            output = stdout.decode("utf-8", errors="replace")

            if parse_json:
                try:
                    return json.loads(output)
                except json.JSONDecodeError as e:
                    self.logger.error(
                        "ffprobe_json_parse_failed",
                        error=str(e),
                        output_length=len(output),
                    )
                    raise FFProbeParseError(f"Failed to parse ffprobe JSON output: {e}")

            return {"output": output}

        except FileNotFoundError:
            raise FFProbeNotFoundError(
                f"ffprobe binary not found at '{self.ffprobe_path}'. "
                "Please install ffmpeg: brew install ffmpeg",
                path=self.ffprobe_path,
            )
        except asyncio.TimeoutError:
            self.logger.error(
                "ffprobe_timeout",
                timeout=self.config.timeout,
            )
            raise FFProbeExecutionError(f"ffprobe command timed out after {self.config.timeout}s")

    async def get_media_info(self, file_path: Path) -> FFProbeMediaInfo:
        """
        Get complete media information for a video file.

        Executes ffprobe with JSON output to retrieve format and stream metadata.
        Parses the output into a structured FFProbeMediaInfo object.

        Args:
            file_path: Path to video file

        Returns:
            FFProbeMediaInfo object with format and stream information

        Raises:
            FFProbeNotFoundError: If ffprobe binary not found
            FFProbeExecutionError: If ffprobe command fails
            FFProbeParseError: If parsing output fails
            FileNotFoundError: If video file doesn't exist

        Example:
            >>> async with FFProbeClient.from_config(config) as client:
            ...     media_info = await client.get_media_info(Path("video.mp4"))
            ...     print(f"Container: {media_info.format.format_name}")
            ...     print(f"Duration: {media_info.format.duration}s")
            ...     video = media_info.get_primary_video_stream()
            ...     if video:
            ...         print(f"Resolution: {video.width}x{video.height}")
            ...         print(f"Codec: {video.codec_name}")
            ...         print(f"Frame rate: {video.get_frame_rate_as_float():.2f} fps")
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Video file not found: {file_path}")

        self.logger.info(
            "ffprobe_get_media_info",
            file_path=str(file_path),
            file_size=file_path.stat().st_size,
        )

        # Build ffprobe command
        args = [
            "-v",
            "quiet",  # Suppress non-error output
            "-print_format",
            "json",  # Output in JSON format
        ]

        if self.config.show_format:
            args.append("-show_format")

        if self.config.show_streams:
            args.append("-show_streams")

        args.append(str(file_path))

        # Execute and parse
        data = await self._execute_ffprobe(args, parse_json=True)

        try:
            media_info = FFProbeParser.parse_media_info(data)
            self.logger.info(
                "ffprobe_parse_complete",
                file_path=str(file_path),
                duration=media_info.format.duration,
                video_streams=len(media_info.video_streams),
                audio_streams=len(media_info.audio_streams),
            )
            return media_info
        except ValueError as e:
            raise FFProbeParseError(f"Failed to parse media info: {e}")
