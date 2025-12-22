"""yt-dlp API request/response schemas."""

from typing import Optional

from pydantic import BaseModel, Field


class YTDLPSearchRequest(BaseModel):
    """Request parameters for YouTube search.

    Attributes:
        artist: Artist name to search for
        track_title: Track/song title to search for
        max_results: Maximum number of results to return (1-50)

    Example:
        >>> request = YTDLPSearchRequest(
        ...     artist="Nirvana",
        ...     track_title="Smells Like Teen Spirit",
        ...     max_results=5
        ... )
    """

    artist: str = Field(
        description="Artist name to search for",
        min_length=1,
        max_length=200,
    )
    track_title: str = Field(
        description="Track/song title to search for",
        min_length=1,
        max_length=200,
    )
    max_results: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of results to return",
    )


class YTDLPVideoInfo(BaseModel):
    """YouTube video metadata response.

    Represents video information returned from yt-dlp.

    Attributes:
        id: YouTube video ID
        title: Video title
        url: Full YouTube URL
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

    model_config = {"extra": "ignore"}


class YTDLPSearchResponse(BaseModel):
    """Response containing YouTube search results.

    Attributes:
        results: List of video metadata results
        query: The search query used (artist + track_title)
        total: Number of results returned
    """

    results: list[YTDLPVideoInfo] = Field(description="List of video search results")
    query: str = Field(description="Search query used")
    total: int = Field(description="Number of results returned")


class YTDLPVideoInfoResponse(BaseModel):
    """Response containing single video metadata.

    Attributes:
        video: Video metadata
    """

    video: YTDLPVideoInfo = Field(description="Video metadata")


class YTDLPDownloadRequest(BaseModel):
    """Request to download a YouTube video.

    Attributes:
        url: YouTube video URL or video ID
        output_path: Path where the video file should be saved (within library_dir)
        format_spec: Optional yt-dlp format specification

    Example:
        >>> request = YTDLPDownloadRequest(
        ...     url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ...     output_path="Rick Astley/Never Gonna Give You Up.mp4"
        ... )
    """

    url: str = Field(
        description="YouTube video URL or video ID",
        min_length=1,
    )
    output_path: str = Field(
        description="Relative path within library directory where the video should be saved",
        min_length=1,
    )
    format_spec: Optional[str] = Field(
        default=None,
        description="yt-dlp format specification (e.g., 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best')",
    )


class YTDLPDownloadProgress(BaseModel):
    """Real-time download progress update (WebSocket message).

    Sent via WebSocket to provide download progress updates.

    Attributes:
        job_id: Associated job ID
        percent: Download completion percentage (0-100)
        downloaded_bytes: Bytes downloaded so far
        total_bytes: Total file size in bytes (None if unknown)
        speed_bytes_per_sec: Current download speed in bytes/second
        eta_seconds: Estimated time remaining in seconds
        status: Current download status
    """

    job_id: str = Field(description="Associated job ID")
    percent: float = Field(description="Download completion percentage (0-100)")
    downloaded_bytes: int = Field(description="Bytes downloaded so far")
    total_bytes: Optional[int] = Field(default=None, description="Total file size in bytes")
    speed_bytes_per_sec: Optional[float] = Field(
        default=None, description="Current download speed in bytes/second"
    )
    eta_seconds: Optional[int] = Field(
        default=None, description="Estimated time remaining in seconds"
    )
    status: str = Field(default="downloading", description="Current download status")


class YTDLPDownloadResult(BaseModel):
    """Download operation result.

    Returned in job result when download completes successfully.

    Attributes:
        url: Source URL that was downloaded
        file_path: Path to the downloaded file
        file_size: File size in bytes
    """

    url: str = Field(description="Source URL that was downloaded")
    file_path: str = Field(description="Path to the downloaded file")
    file_size: int = Field(description="File size in bytes", ge=0)
