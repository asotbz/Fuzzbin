"""Exceptions for core business logic."""

from pathlib import Path
from typing import Optional


class OrganizerError(Exception):
    """Base exception for organizer errors."""

    pass


class InvalidPatternError(OrganizerError):
    """Raised when pattern contains invalid field names or syntax."""

    def __init__(self, message: str, pattern: Optional[str] = None):
        super().__init__(message)
        self.pattern = pattern


class MissingFieldError(OrganizerError):
    """Raised when required pattern field is None or empty in NFO data."""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.field = field


class InvalidPathError(OrganizerError):
    """Raised when root_path is invalid or inaccessible."""

    def __init__(self, message: str, path: Optional[Path] = None):
        super().__init__(message)
        self.path = path


# yt-dlp exceptions
class YTDLPError(Exception):
    """Base exception for yt-dlp errors."""

    pass


class YTDLPNotFoundError(YTDLPError):
    """Raised when yt-dlp binary is not found."""

    def __init__(self, message: str, path: Optional[str] = None):
        super().__init__(message)
        self.path = path


class YTDLPExecutionError(YTDLPError):
    """Raised when yt-dlp command execution fails."""

    def __init__(
        self,
        message: str,
        returncode: Optional[int] = None,
        stderr: Optional[str] = None,
    ):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class YTDLPParseError(YTDLPError):
    """Raised when parsing yt-dlp output fails."""

    pass


class DownloadCancelledError(YTDLPError):
    """Raised when a download is cancelled via CancellationToken."""

    pass


# ffprobe exceptions
class FFProbeError(Exception):
    """Base exception for ffprobe errors."""

    pass


class FFProbeNotFoundError(FFProbeError):
    """Raised when ffprobe binary is not found."""

    def __init__(self, message: str, path: Optional[str] = None):
        super().__init__(message)
        self.path = path


class FFProbeExecutionError(FFProbeError):
    """Raised when ffprobe command execution fails."""

    def __init__(
        self,
        message: str,
        returncode: Optional[int] = None,
        stderr: Optional[str] = None,
    ):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class FFProbeParseError(FFProbeError):
    """Raised when parsing ffprobe output fails."""

    pass


# ffmpeg exceptions
class FFmpegError(Exception):
    """Base exception for ffmpeg errors."""

    pass


class FFmpegNotFoundError(FFmpegError):
    """Raised when ffmpeg binary is not found."""

    def __init__(self, message: str, path: Optional[str] = None):
        super().__init__(message)
        self.path = path


class FFmpegExecutionError(FFmpegError):
    """Raised when ffmpeg command execution fails."""

    def __init__(
        self,
        message: str,
        returncode: Optional[int] = None,
        stderr: Optional[str] = None,
    ):
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


class ThumbnailTooLargeError(FFmpegError):
    """Raised when generated thumbnail exceeds size limit."""

    def __init__(self, message: str, size: int, max_size: int):
        super().__init__(message)
        self.size = size
        self.max_size = max_size
