"""yt-dlp CLI client for YouTube video search and download."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import structlog

from ..common.config import YTDLPConfig
from ..core.exceptions import (
    DownloadCancelledError,
    InvalidPathError,
    YTDLPError,
    YTDLPExecutionError,
    YTDLPNotFoundError,
    YTDLPParseError,
)
from ..parsers.ytdlp_models import (
    CancellationToken,
    DownloadHooks,
    DownloadProgress,
    YTDLPDownloadResult,
    YTDLPSearchResult,
)

logger = structlog.get_logger(__name__)


class YTDLPClient:
    """
    Async client for yt-dlp CLI tool.

    Provides search and download functionality for YouTube videos with fully async
    subprocess execution. Supports configurable format selection, geographic bypass,
    and timeout controls.

    **Requirements:**
        The yt-dlp binary must be installed separately and available in PATH.
        Install via: `pip install yt-dlp` or `brew install yt-dlp`

    Features:
    - Search YouTube by artist and track title
    - Download videos in best quality MP4 format
    - Real-time progress monitoring with hooks
    - Download cancellation support
    - Non-blocking async subprocess execution
    - Configurable timeout and format specifications
    - Structured logging with operation context

    Example:
        >>> import asyncio
        >>> from pathlib import Path
        >>> from fuzzbin.clients.ytdlp_client import YTDLPClient
        >>> from fuzzbin.common.config import YTDLPConfig
        >>>
        >>> async def main():
        ...     config = YTDLPConfig(search_max_results=5)
        ...
        ...     async with YTDLPClient.from_config(config) as client:
        ...         # Search for videos
        ...         results = await client.search("Robin Thicke", "Blurred Lines")
        ...         print(f"Found {len(results)} results")
        ...
        ...         # Download the first result
        ...         if results:
        ...             output_path = Path("downloads/video.mp4")
        ...             output_path.parent.mkdir(exist_ok=True)
        ...             result = await client.download(results[0].url, output_path)
        ...             print(f"Downloaded: {result.file_size} bytes")
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        config: Optional[YTDLPConfig] = None,
        ytdlp_path: str = "yt-dlp",
    ):
        """
        Initialize the yt-dlp client.

        Args:
            config: YTDLPConfig instance for client configuration
            ytdlp_path: Path to yt-dlp binary (default: "yt-dlp" from PATH)
        """
        self.config = config or YTDLPConfig()
        self.ytdlp_path = ytdlp_path
        self.logger = structlog.get_logger(__name__)

    async def __aenter__(self) -> "YTDLPClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        pass

    @classmethod
    def from_config(cls, config: YTDLPConfig) -> "YTDLPClient":
        """
        Create YTDLPClient from YTDLPConfig.

        Args:
            config: YTDLPConfig instance

        Returns:
            YTDLPClient instance configured from config

        Example:
            >>> from fuzzbin.common.config import YTDLPConfig
            >>> config = YTDLPConfig(timeout=600)
            >>> async with YTDLPClient.from_config(config) as client:
            ...     results = await client.search("Artist", "Track")
        """
        return cls(config=config, ytdlp_path=config.ytdlp_path)

    async def _execute_ytdlp(
        self,
        args: List[str],
        capture_json: bool = False,
    ) -> Union[str, Dict[str, Any]]:
        """
        Execute yt-dlp command asynchronously.

        Uses asyncio.create_subprocess_exec() for non-blocking subprocess execution.
        Handles command errors, timeouts, and JSON parsing.

        Args:
            args: Command line arguments for yt-dlp
            capture_json: If True, parse stdout as JSON

        Returns:
            Command output (string) or parsed JSON dict

        Raises:
            YTDLPNotFoundError: If yt-dlp binary not found
            YTDLPExecutionError: If command fails or times out
            YTDLPParseError: If JSON parsing fails
        """
        cmd = [self.ytdlp_path] + args

        self.logger.debug(
            "ytdlp_execute",
            command=" ".join(cmd),
            capture_json=capture_json,
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
                    "ytdlp_failed",
                    returncode=process.returncode,
                    stderr=error_msg[:500],  # Truncate long errors
                )
                raise YTDLPExecutionError(
                    f"yt-dlp failed with exit code {process.returncode}",
                    returncode=process.returncode,
                    stderr=error_msg,
                )

            output = stdout.decode("utf-8", errors="replace")

            if capture_json:
                try:
                    return json.loads(output)
                except json.JSONDecodeError as e:
                    raise YTDLPParseError(f"Failed to parse JSON: {e}")

            return output

        except FileNotFoundError:
            raise YTDLPNotFoundError(
                f"yt-dlp binary not found at '{self.ytdlp_path}'. "
                "Please install yt-dlp: pip install yt-dlp"
            )
        except asyncio.TimeoutError:
            raise YTDLPExecutionError("Command timed out")

    async def search(
        self,
        artist: str,
        track_title: str,
        max_results: int = 5,
    ) -> List[YTDLPSearchResult]:
        """
        Search YouTube for music videos.

        Executes yt-dlp with --dump-json and --flat-playlist to retrieve search
        results without downloading videos. Returns metadata for the top matching
        videos.

        Args:
            artist: Artist name
            track_title: Track title
            max_results: Maximum number of results to return (default: 5)

        Returns:
            List of YTDLPSearchResult objects sorted by relevance

        Raises:
            YTDLPNotFoundError: If yt-dlp binary not found
            YTDLPExecutionError: If search fails

        Example:
            >>> async with YTDLPClient.from_config(config) as client:
            ...     results = await client.search("Bush", "Machinehead", max_results=3)
            ...     for result in results:
            ...         print(f"{result.title} - {result.view_count:,} views")
        """
        query = f"{artist} {track_title}"
        search_query = f"ytsearch{max_results}:{query}"

        self.logger.info(
            "ytdlp_search",
            artist=artist,
            track_title=track_title,
            max_results=max_results,
        )

        # Build command args
        args = [
            "--dump-json",  # Output JSON metadata
            "--flat-playlist",  # Don't download, just get metadata
            "--no-warnings",  # Suppress warnings
            search_query,
        ]

        # Add config options
        if self.config.geo_bypass:
            args.append("--geo-bypass")

        # Execute and get newline-delimited JSON output
        output = await self._execute_ytdlp(args, capture_json=False)

        # Parse newline-delimited JSON (one JSON object per line)
        results = []
        for line in output.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                results.append(YTDLPSearchResult.from_dict(data))
            except json.JSONDecodeError:
                self.logger.warning("ytdlp_parse_error", line=line[:100])
                continue

        self.logger.info(
            "ytdlp_search_complete",
            results_found=len(results),
            query=query,
        )

        return results

    async def _call_hook(
        self, hook: Optional[Callable], *args: Any
    ) -> None:
        """
        Call a hook function, handling both sync and async callbacks.

        Args:
            hook: Callback function (sync or async)
            *args: Arguments to pass to the callback

        Raises:
            Exception: Any exception raised by the hook
        """
        if hook is None:
            return

        try:
            result = hook(*args)
            # Check if result is a coroutine (async function)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            self.logger.error("hook_error", hook=hook.__name__, error=str(e))
            raise

    def _parse_size(self, size_str: str) -> Optional[int]:
        """
        Parse file size string to bytes.

        Args:
            size_str: Size string like "10.5MiB", "1.2GiB", "500KiB"

        Returns:
            Size in bytes, or None if parsing fails

        Example:
            >>> client._parse_size("10.5MiB")
            11010048
        """
        if not size_str:
            return None

        size_str = size_str.strip()
        match = re.match(r"([\d.]+)\s*([KMGT]i?B)", size_str, re.IGNORECASE)
        if not match:
            return None

        value = float(match.group(1))
        unit = match.group(2).upper()

        # Convert to bytes
        multipliers = {
            "B": 1,
            "KB": 1000,
            "KIB": 1024,
            "MB": 1000**2,
            "MIB": 1024**2,
            "GB": 1000**3,
            "GIB": 1024**3,
            "TB": 1000**4,
            "TIB": 1024**4,
        }

        return int(value * multipliers.get(unit, 1))

    def _parse_speed(self, speed_str: str) -> Optional[float]:
        """
        Parse download speed string to bytes per second.

        Args:
            speed_str: Speed string like "1.2MiB/s", "500KiB/s"

        Returns:
            Speed in bytes per second, or None if parsing fails
        """
        if not speed_str:
            return None

        # Remove /s suffix
        speed_str = speed_str.replace("/s", "").strip()
        size_bytes = self._parse_size(speed_str)
        return float(size_bytes) if size_bytes else None

    def _parse_eta(self, eta_str: str) -> Optional[int]:
        """
        Parse ETA string to seconds.

        Args:
            eta_str: ETA string like "00:04", "01:23", "Unknown ETA"

        Returns:
            ETA in seconds, or None if unknown
        """
        if not eta_str or "unknown" in eta_str.lower():
            return None

        # Parse MM:SS format
        match = re.match(r"(\d+):(\d+)", eta_str)
        if match:
            minutes = int(match.group(1))
            seconds = int(match.group(2))
            return minutes * 60 + seconds

        return None

    def _parse_progress_line(self, line: str) -> Optional[DownloadProgress]:
        """
        Parse yt-dlp progress output line.

        Args:
            line: Progress line from yt-dlp stdout

        Returns:
            DownloadProgress object if line contains progress info, None otherwise

        Example line formats:
            [download]  45.2% of 10.5MiB at 1.2MiB/s ETA 00:04
            [download] 100% of 10.5MiB in 00:08
        """
        if "[download]" not in line:
            return None

        # Try to parse percentage
        percent_match = re.search(r"([\d.]+)%", line)
        if not percent_match:
            return None

        percent = float(percent_match.group(1))

        # Parse total size
        total_bytes = None
        size_match = re.search(r"of\s+([\d.]+\s*[KMGT]i?B)", line)
        if size_match:
            total_bytes = self._parse_size(size_match.group(1))

        # Calculate downloaded bytes
        downloaded_bytes = 0
        if total_bytes:
            downloaded_bytes = int(total_bytes * percent / 100)

        # Parse speed
        speed_bytes_per_sec = None
        speed_match = re.search(r"at\s+([\d.]+\s*[KMGT]i?B/s)", line)
        if speed_match:
            speed_bytes_per_sec = self._parse_speed(speed_match.group(1))

        # Parse ETA
        eta_seconds = None
        eta_match = re.search(r"ETA\s+([\d:]+|Unknown)", line)
        if eta_match:
            eta_seconds = self._parse_eta(eta_match.group(1))

        # Determine status
        status = "downloading"
        if percent >= 100.0:
            status = "finished"

        return DownloadProgress(
            percent=percent,
            downloaded_bytes=downloaded_bytes,
            total_bytes=total_bytes,
            speed_bytes_per_sec=speed_bytes_per_sec,
            eta_seconds=eta_seconds,
            status=status,
        )

    async def _download_with_progress(
        self,
        url: str,
        output_path: Path,
        format_spec: str,
        hooks: Optional[DownloadHooks] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        """
        Download video with real-time progress monitoring, hooks, and cancellation support.

        Args:
            url: YouTube video URL
            output_path: Destination path for downloaded file
            format_spec: Format specification for yt-dlp
            hooks: Optional lifecycle hooks for download events
            cancellation_token: Optional token for cancelling the download

        Raises:
            YTDLPNotFoundError: If yt-dlp binary not found
            YTDLPExecutionError: If download fails
            DownloadCancelledError: If download is cancelled via cancellation_token
        """
        # Build command args
        args = [
            "--format",
            format_spec,
            "--output",
            str(output_path),
            "--no-playlist",
            "--newline",  # Force newlines for progress updates
            url,
        ]

        # Add config options
        if self.config.geo_bypass:
            args.append("--geo-bypass")

        cmd = [self.ytdlp_path] + args

        self.logger.debug(
            "ytdlp_download_with_progress",
            command=" ".join(cmd),
        )

        # Check for early cancellation
        if cancellation_token and cancellation_token.is_cancelled():
            self.logger.info("ytdlp_download_cancelled_before_start")
            raise DownloadCancelledError("Download was cancelled before starting")

        # Call on_start hook
        if hooks:
            await self._call_hook(hooks.on_start)

        process = None
        try:
            # Start subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Read stdout line by line
            if process.stdout:
                async for line in process.stdout:
                    # Check for cancellation
                    if cancellation_token and cancellation_token.is_cancelled():
                        self.logger.info("ytdlp_download_cancelled")
                        # Kill the process
                        process.kill()
                        await process.wait()
                        raise DownloadCancelledError("Download was cancelled by user")

                    decoded = line.decode("utf-8", errors="replace").strip()

                    # Parse progress lines
                    progress = self._parse_progress_line(decoded)
                    if progress:
                        # Call on_progress hook
                        if hooks:
                            await self._call_hook(hooks.on_progress, progress)

                    # Log non-progress lines at debug level
                    if not decoded.startswith("[download]"):
                        self.logger.debug("ytdlp_output", line=decoded)

            # Wait for completion
            await process.wait()

            if process.returncode != 0:
                stderr = await process.stderr.read() if process.stderr else b""
                error_msg = stderr.decode("utf-8", errors="replace")
                self.logger.error(
                    "ytdlp_download_failed",
                    returncode=process.returncode,
                    stderr=error_msg[:500],
                )
                error = YTDLPExecutionError(
                    f"yt-dlp failed with exit code {process.returncode}",
                    returncode=process.returncode,
                    stderr=error_msg,
                )
                # Call on_error hook
                if hooks:
                    await self._call_hook(hooks.on_error, error)
                raise error

        except YTDLPExecutionError:
            # Already called on_error, just re-raise
            raise
        except FileNotFoundError:
            error = YTDLPNotFoundError(
                f"yt-dlp binary not found at '{self.ytdlp_path}'. "
                "Please install yt-dlp: pip install yt-dlp"
            )
            # Call on_error hook
            if hooks:
                await self._call_hook(hooks.on_error, error)
            raise
        except YTDLPNotFoundError:
            # Already called on_error, just re-raise
            raise
        except DownloadCancelledError:
            # Don't call on_error for cancellation, just re-raise
            raise
        except Exception as e:
            # Call on_error hook for any other exceptions
            if hooks:
                await self._call_hook(hooks.on_error, e)
            raise
        finally:
            # Ensure process is terminated if still running
            if process and process.returncode is None:
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass

    async def download(
        self,
        url: str,
        output_path: Path,
        format_spec: Optional[str] = None,
        progress_callback: Optional[Callable[[DownloadProgress], Union[None, Awaitable[None]]]] = None,
        hooks: Optional[DownloadHooks] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> YTDLPDownloadResult:
        """
        Download video from URL to specified path.

        Downloads best quality MP4 video by default. Uses asyncio subprocess for
        non-blocking execution. Supports progress monitoring, lifecycle hooks,
        and cancellation.

        Args:
            url: YouTube video URL
            output_path: Destination path for downloaded file
            format_spec: Custom format specification (default: from config)
            progress_callback: Optional callback for progress updates (sync or async).
                Called with DownloadProgress objects during download.
                DEPRECATED: Use hooks.on_progress instead.
            hooks: Optional DownloadHooks with lifecycle callbacks
                (on_start, on_progress, on_complete, on_error)
            cancellation_token: Optional CancellationToken for cancelling download

        Returns:
            YTDLPDownloadResult with download metadata

        Raises:
            YTDLPNotFoundError: If yt-dlp binary not found
            YTDLPExecutionError: If download fails
            InvalidPathError: If output_path parent doesn't exist
            DownloadCancelledError: If download is cancelled via cancellation_token

        Example (basic):
            >>> output_path = Path("downloads/video.mp4")
            >>> output_path.parent.mkdir(exist_ok=True)
            >>>
            >>> async with YTDLPClient.from_config(config) as client:
            ...     result = await client.download(
            ...         "https://www.youtube.com/watch?v=test",
            ...         output_path
            ...     )
            ...     print(f"Downloaded {result.file_size / (1024 * 1024):.2f} MB")

        Example (with hooks):
            >>> async def on_start():
            ...     print("Starting download...")
            >>>
            >>> async def on_progress(progress: DownloadProgress):
            ...     print(f"Progress: {progress.percent:.1f}%")
            >>>
            >>> async def on_complete(result: YTDLPDownloadResult):
            ...     print(f"Downloaded {result.file_size} bytes")
            >>>
            >>> hooks = DownloadHooks(
            ...     on_start=on_start,
            ...     on_progress=on_progress,
            ...     on_complete=on_complete,
            ... )
            >>>
            >>> async with YTDLPClient.from_config(config) as client:
            ...     result = await client.download(url, output_path, hooks=hooks)

        Example (with cancellation):
            >>> token = CancellationToken()
            >>>
            >>> def on_progress(progress: DownloadProgress):
            ...     if progress.percent > 50:
            ...         token.cancel()  # Cancel after 50%
            >>>
            >>> hooks = DownloadHooks(on_progress=on_progress)
            >>>
            >>> try:
            ...     result = await client.download(
            ...         url, output_path,
            ...         hooks=hooks,
            ...         cancellation_token=token
            ...     )
            ... except DownloadCancelledError:
            ...     print("Download cancelled!")
        """
        # Validate output path
        if not output_path.parent.exists():
            raise InvalidPathError(
                f"Output directory does not exist: {output_path.parent}",
                path=output_path.parent,
            )

        self.logger.info(
            "ytdlp_download",
            url=url,
            output_path=str(output_path),
            with_hooks=hooks is not None,
            with_cancellation=cancellation_token is not None,
        )

        # Use config format or provided format_spec or default
        format_spec = format_spec or self.config.format_spec

        # Merge progress_callback into hooks for backward compatibility
        if progress_callback is not None:
            if hooks is None:
                hooks = DownloadHooks(on_progress=progress_callback)
            elif hooks.on_progress is None:
                hooks.on_progress = progress_callback

        # Use progress monitoring if hooks or cancellation_token provided
        if hooks is not None or cancellation_token is not None:
            await self._download_with_progress(
                url,
                output_path,
                format_spec,
                hooks,
                cancellation_token,
            )
        else:
            # Use simple download without progress monitoring
            args = [
                "--format",
                format_spec,
                "--output",
                str(output_path),
                "--no-playlist",  # Only download single video
                "--no-warnings",
                url,
            ]

            # Add config options
            if self.config.geo_bypass:
                args.append("--geo-bypass")
            if self.config.quiet:
                args.append("--quiet")
            else:
                args.append("--progress")

            # Execute download
            await self._execute_ytdlp(args, capture_json=False)

        # Verify file was created
        if not output_path.exists():
            raise YTDLPExecutionError(
                f"Download completed but file not found at {output_path}"
            )

        file_size = output_path.stat().st_size

        self.logger.info(
            "ytdlp_download_complete",
            url=url,
            output_path=str(output_path),
            file_size_mb=round(file_size / (1024 * 1024), 2),
        )

        result = YTDLPDownloadResult(
            url=url,
            output_path=output_path,
            file_size=file_size,
        )

        # Call on_complete hook
        if hooks:
            await self._call_hook(hooks.on_complete, result)

        return result
