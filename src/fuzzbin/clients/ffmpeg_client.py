"""ffmpeg CLI client for video thumbnail extraction."""

import asyncio
import shutil
from pathlib import Path
from typing import Any, Optional

import structlog

from ..common.config import ThumbnailConfig
from ..core.exceptions import (
    FFmpegError,
    FFmpegExecutionError,
    FFmpegNotFoundError,
    ThumbnailTooLargeError,
)

logger = structlog.get_logger(__name__)


class FFmpegClient:
    """
    Async client for ffmpeg CLI tool focused on thumbnail generation.

    Provides video frame extraction functionality with fully async
    subprocess execution. Extracts a single frame from a video file
    and saves it as a JPEG thumbnail.

    **Requirements:**
        The ffmpeg binary must be installed separately and available in PATH.
        Install via: `brew install ffmpeg` or download from ffmpeg.org

    Features:
    - Extract single frame as JPEG thumbnail
    - Configurable timestamp, resolution, and quality
    - Output file size safety check
    - Non-blocking async subprocess execution
    - Configurable timeout
    - Structured logging with operation context

    Example:
        >>> import asyncio
        >>> from pathlib import Path
        >>> from fuzzbin.clients.ffmpeg_client import FFmpegClient
        >>> from fuzzbin.common.config import ThumbnailConfig
        >>>
        >>> async def main():
        ...     config = ThumbnailConfig()
        ...
        ...     async with FFmpegClient.from_config(config) as client:
        ...         video_path = Path("downloads/video.mp4")
        ...         thumb_path = Path(".thumbnails/1.jpg")
        ...         
        ...         result = await client.extract_frame(
        ...             video_path=video_path,
        ...             output_path=thumb_path,
        ...         )
        ...         print(f"Thumbnail created: {result}")
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        config: Optional[ThumbnailConfig] = None,
        ffmpeg_path: str = "ffmpeg",
    ):
        """
        Initialize the ffmpeg client.

        Args:
            config: ThumbnailConfig instance for client configuration
            ffmpeg_path: Path to ffmpeg binary (default: "ffmpeg" from PATH)
        """
        self.config = config or ThumbnailConfig()
        self.ffmpeg_path = ffmpeg_path
        self.logger = structlog.get_logger(__name__)
        self._verified = False

    async def __aenter__(self) -> "FFmpegClient":
        """Async context manager entry."""
        await self._verify_binary()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        pass

    @classmethod
    def from_config(cls, config: ThumbnailConfig) -> "FFmpegClient":
        """
        Create FFmpegClient from ThumbnailConfig.

        Args:
            config: ThumbnailConfig instance

        Returns:
            FFmpegClient instance configured from config

        Example:
            >>> from fuzzbin.common.config import ThumbnailConfig
            >>> config = ThumbnailConfig(width=320, height=180)
            >>> async with FFmpegClient.from_config(config) as client:
            ...     await client.extract_frame(video_path, output_path)
        """
        return cls(config=config, ffmpeg_path=config.ffmpeg_path)

    async def _verify_binary(self) -> None:
        """
        Verify that ffmpeg binary exists and is executable.

        Raises:
            FFmpegNotFoundError: If ffmpeg binary not found in PATH
        """
        if self._verified:
            return

        # Check if binary exists in PATH
        if not shutil.which(self.ffmpeg_path):
            raise FFmpegNotFoundError(
                f"ffmpeg binary not found at '{self.ffmpeg_path}'. "
                "Please install ffmpeg: brew install ffmpeg",
                path=self.ffmpeg_path,
            )

        self.logger.debug(
            "ffmpeg_binary_verified",
            path=self.ffmpeg_path,
        )
        self._verified = True

    async def extract_frame(
        self,
        video_path: Path,
        output_path: Path,
        timestamp: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Path:
        """
        Extract a single frame from a video file as a JPEG thumbnail.

        Uses ffmpeg to seek to a specified timestamp and extract a single
        frame, optionally scaling it to a specified resolution.

        Args:
            video_path: Path to source video file
            output_path: Path for output JPEG file
            timestamp: Time in seconds to extract frame from (default: config.default_timestamp)
            width: Output width in pixels (default: config.width)
            height: Output height in pixels (default: config.height)

        Returns:
            Path to the created thumbnail file

        Raises:
            FFmpegNotFoundError: If ffmpeg binary not found
            FFmpegExecutionError: If ffmpeg command fails
            ThumbnailTooLargeError: If output file exceeds max_file_size
            FileNotFoundError: If video file doesn't exist

        Example:
            >>> async with FFmpegClient.from_config(config) as client:
            ...     thumb = await client.extract_frame(
            ...         video_path=Path("video.mp4"),
            ...         output_path=Path(".thumbnails/1.jpg"),
            ...         timestamp=5.0,
            ...     )
        """
        await self._verify_binary()

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Use config defaults if not specified
        timestamp = timestamp if timestamp is not None else self.config.default_timestamp
        width = width or self.config.width
        height = height or self.config.height

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build ffmpeg command
        # -ss before -i for fast seeking
        # -frames:v 1 to extract single frame
        # -vf scale for resolution
        # -q:v 2-5 for JPEG quality (2 = best, 31 = worst)
        cmd = [
            self.ffmpeg_path,
            "-y",  # Overwrite output file if exists
            "-ss", str(timestamp),  # Seek to timestamp (before input for fast seek)
            "-i", str(video_path),  # Input file
            "-frames:v", "1",  # Extract single frame
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease",
            "-q:v", str(self.config.quality),  # JPEG quality
            str(output_path),
        ]

        self.logger.info(
            "ffmpeg_extract_frame_start",
            video_path=str(video_path),
            output_path=str(output_path),
            timestamp=timestamp,
            resolution=f"{width}x{height}",
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.config.timeout,
            )

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")
                self.logger.error(
                    "ffmpeg_extract_frame_failed",
                    returncode=process.returncode,
                    stderr=error_msg[:500],  # Truncate long errors
                )
                raise FFmpegExecutionError(
                    f"ffmpeg failed with exit code {process.returncode}",
                    returncode=process.returncode,
                    stderr=error_msg,
                )

            # Verify output file was created
            if not output_path.exists():
                raise FFmpegExecutionError(
                    f"ffmpeg completed but output file not found: {output_path}"
                )

            # Safety check: verify output file size
            output_size = output_path.stat().st_size
            if output_size > self.config.max_file_size:
                # Delete the oversized file
                output_path.unlink()
                self.logger.error(
                    "thumbnail_too_large",
                    output_path=str(output_path),
                    size=output_size,
                    max_size=self.config.max_file_size,
                )
                raise ThumbnailTooLargeError(
                    f"Generated thumbnail ({output_size} bytes) exceeds "
                    f"max size ({self.config.max_file_size} bytes)",
                    size=output_size,
                    max_size=self.config.max_file_size,
                )

            self.logger.info(
                "ffmpeg_extract_frame_complete",
                video_path=str(video_path),
                output_path=str(output_path),
                output_size=output_size,
            )

            return output_path

        except FileNotFoundError:
            raise FFmpegNotFoundError(
                f"ffmpeg binary not found at '{self.ffmpeg_path}'. "
                "Please install ffmpeg: brew install ffmpeg",
                path=self.ffmpeg_path,
            )
        except asyncio.TimeoutError:
            # Clean up partial output if any
            if output_path.exists():
                output_path.unlink()
            self.logger.error(
                "ffmpeg_timeout",
                timeout=self.config.timeout,
            )
            raise FFmpegExecutionError(
                f"ffmpeg command timed out after {self.config.timeout}s"
            )
