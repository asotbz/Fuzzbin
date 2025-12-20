"""Pydantic models for yt-dlp metadata."""

from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Optional, Union

from pydantic import BaseModel, Field


class YTDLPSearchResult(BaseModel):
    """Model for YouTube search result metadata.

    Represents a single video search result from yt-dlp with key metadata
    fields for identifying and evaluating videos.

    Attributes:
        id: YouTube video ID
        title: Video title
        url: Full YouTube URL (webpage_url)
        channel: Channel name
        channel_follower_count: Channel subscriber count
        view_count: Video view count
        duration: Video duration in seconds
    """

    id: str = Field(description="YouTube video ID")
    title: str = Field(description="Video title")
    url: str = Field(description="Full YouTube URL")
    channel: Optional[str] = Field(default=None, description="Channel name")
    channel_follower_count: Optional[int] = Field(
        default=None, description="Channel subscriber count"
    )
    view_count: Optional[int] = Field(default=None, description="Video view count")
    duration: Optional[int] = Field(default=None, description="Video duration in seconds")

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
    }

    @classmethod
    def from_dict(cls, data: dict) -> "YTDLPSearchResult":
        """Create YTDLPSearchResult from yt-dlp JSON output.

        Args:
            data: Dictionary from yt-dlp --dump-json output

        Returns:
            YTDLPSearchResult instance with parsed metadata

        Example:
            >>> data = {
            ...     "id": "5WPbqYoz9HA",
            ...     "title": "Bush - Machinehead",
            ...     "webpage_url": "https://www.youtube.com/watch?v=5WPbqYoz9HA",
            ...     "channel": "Bush",
            ...     "channel_follower_count": 411000,
            ...     "view_count": 28794614,
            ...     "duration": 257
            ... }
            >>> result = YTDLPSearchResult.from_dict(data)
            >>> result.title
            'Bush - Machinehead'
        """
        return cls(
            id=data["id"],
            title=data["title"],
            url=data.get("webpage_url", f"https://www.youtube.com/watch?v={data['id']}"),
            channel=data.get("channel"),
            channel_follower_count=data.get("channel_follower_count"),
            view_count=data.get("view_count"),
            duration=data.get("duration"),
        )


class YTDLPDownloadResult(BaseModel):
    """Model for yt-dlp download operation result.

    Represents the outcome of a successful video download operation,
    containing metadata about the downloaded file.

    Attributes:
        url: Source URL that was downloaded
        output_path: Path to the downloaded file
        file_size: File size in bytes
    """

    url: str = Field(description="Source URL")
    output_path: Path = Field(description="Path to downloaded file")
    file_size: int = Field(description="File size in bytes", ge=0)

    model_config = {
        "extra": "ignore",
        "validate_assignment": True,
        "arbitrary_types_allowed": True,  # Required for Path type
    }


@dataclass
class DownloadProgress:
    """Real-time download progress information.

    This dataclass represents the current state of a download operation,
    parsed from yt-dlp's progress output.

    Attributes:
        percent: Download completion percentage (0-100)
        downloaded_bytes: Number of bytes downloaded so far
        total_bytes: Total file size in bytes (None if unknown)
        speed_bytes_per_sec: Current download speed in bytes/second (None if unknown)
        eta_seconds: Estimated time remaining in seconds (None if unknown)
        status: Current download status (downloading, finished, error, etc.)

    Example:
        >>> progress = DownloadProgress(
        ...     percent=45.2,
        ...     downloaded_bytes=4_750_000,
        ...     total_bytes=10_500_000,
        ...     speed_bytes_per_sec=1_200_000,
        ...     eta_seconds=4
        ... )
        >>> print(f"{progress.percent:.1f}% at {progress.speed_bytes_per_sec / (1024**2):.2f} MB/s")
        45.2% at 1.14 MB/s
    """

    percent: float
    downloaded_bytes: int
    total_bytes: Optional[int] = None
    speed_bytes_per_sec: Optional[float] = None
    eta_seconds: Optional[int] = None
    status: str = "downloading"


class CancellationToken:
    """Token for cancelling download operations.

    Provides a thread-safe way to signal download cancellation.
    Can be passed to download methods and checked from callbacks.

    Example:
        >>> token = CancellationToken()
        >>> def on_progress(progress):
        ...     if progress.percent > 50:
        ...         token.cancel()  # Cancel after 50%
        >>>
        >>> try:
        ...     await client.download(url, path, cancellation_token=token)
        ... except DownloadCancelledError:
        ...     print("Download was cancelled")
    """

    def __init__(self) -> None:
        """Initialize cancellation token."""
        self._cancelled = False

    def cancel(self) -> None:
        """Signal cancellation."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancelled

    def reset(self) -> None:
        """Reset the cancellation state."""
        self._cancelled = False


@dataclass
class DownloadHooks:
    """Collection of lifecycle hooks for download operations.

    Provides callbacks for different stages of the download process.
    All callbacks can be either sync or async functions.

    Attributes:
        on_start: Called when download begins (before any data transfer)
        on_progress: Called with DownloadProgress objects during download
        on_complete: Called when download completes successfully
        on_error: Called if download fails with an exception

    Example:
        >>> async def on_start():
        ...     print("Starting download...")
        >>>
        >>> def on_progress(progress: DownloadProgress):
        ...     print(f"Progress: {progress.percent:.1f}%")
        >>>
        >>> async def on_complete(result: YTDLPDownloadResult):
        ...     print(f"Downloaded {result.file_size} bytes")
        >>>
        >>> def on_error(error: Exception):
        ...     print(f"Download failed: {error}")
        >>>
        >>> hooks = DownloadHooks(
        ...     on_start=on_start,
        ...     on_progress=on_progress,
        ...     on_complete=on_complete,
        ...     on_error=on_error,
        ... )
        >>>
        >>> await client.download(url, path, hooks=hooks)
    """

    on_start: Optional[Callable[[], Union[None, Awaitable[None]]]] = None
    on_progress: Optional[Callable[[DownloadProgress], Union[None, Awaitable[None]]]] = None
    on_complete: Optional[Callable[["YTDLPDownloadResult"], Union[None, Awaitable[None]]]] = None
    on_error: Optional[Callable[[Exception], Union[None, Awaitable[None]]]] = None
