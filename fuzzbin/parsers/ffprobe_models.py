"""Pydantic models for ffprobe JSON output."""

from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class FFProbeFormat(BaseModel):
    """Container format information from ffprobe."""

    filename: str
    format_name: str
    format_long_name: Optional[str] = None
    duration: Optional[float] = None
    size: Optional[int] = Field(None, alias="size")
    bit_rate: Optional[int] = Field(None, alias="bit_rate")
    nb_streams: Optional[int] = None
    tags: Optional[dict] = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("size", "bit_rate", mode="before")
    @classmethod
    def parse_string_int(cls, v: Any) -> Optional[int]:
        """Convert string integers to int."""
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        return v if v is None else int(v) if v is None else int(v)

    @field_validator("duration", mode="before")
    @classmethod
    def parse_string_float(cls, v: Any) -> Optional[float]:
        """Convert string floats to float."""
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return v if v is None else float(v)


class FFProbeVideoStream(BaseModel):
    """Video stream information from ffprobe."""

    index: int
    codec_name: str
    codec_long_name: Optional[str] = None
    codec_type: str = "video"
    width: int
    height: int
    coded_width: Optional[int] = None
    coded_height: Optional[int] = None
    display_aspect_ratio: Optional[str] = None
    r_frame_rate: str  # e.g., "30/1", "30000/1001"
    avg_frame_rate: Optional[str] = None
    time_base: Optional[str] = None
    duration: Optional[float] = None
    bit_rate: Optional[int] = Field(None, alias="bit_rate")
    bits_per_raw_sample: Optional[str] = None
    nb_frames: Optional[int] = Field(None, alias="nb_frames")
    pix_fmt: Optional[str] = None
    level: Optional[int] = None
    tags: Optional[dict] = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("bit_rate", "nb_frames", mode="before")
    @classmethod
    def parse_string_int(cls, v: Any) -> Optional[int]:
        """Convert string integers to int."""
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        return v if v is None else int(v)

    @field_validator("duration", mode="before")
    @classmethod
    def parse_string_float(cls, v: Any) -> Optional[float]:
        """Convert string floats to float."""
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return v if v is None else float(v)

    def get_frame_rate_as_float(self) -> Optional[float]:
        """
        Convert r_frame_rate fraction string to float.

        Returns:
            Frame rate as float (e.g., 29.97), or None if parsing fails.

        Example:
            >>> stream = FFProbeVideoStream(r_frame_rate="30000/1001", ...)
            >>> stream.get_frame_rate_as_float()
            29.97002997002997
        """
        if not self.r_frame_rate:
            return None
        try:
            if "/" in self.r_frame_rate:
                numerator, denominator = self.r_frame_rate.split("/")
                return float(numerator) / float(denominator)
            else:
                return float(self.r_frame_rate)
        except (ValueError, ZeroDivisionError):
            return None


class FFProbeAudioStream(BaseModel):
    """Audio stream information from ffprobe."""

    index: int
    codec_name: str
    codec_long_name: Optional[str] = None
    codec_type: str = "audio"
    sample_rate: str  # e.g., "44100", "48000"
    channels: int
    channel_layout: Optional[str] = None
    bits_per_sample: Optional[int] = None
    bit_rate: Optional[int] = Field(None, alias="bit_rate")
    duration: Optional[float] = None
    nb_frames: Optional[int] = Field(None, alias="nb_frames")
    tags: Optional[dict] = None

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("bit_rate", "nb_frames", mode="before")
    @classmethod
    def parse_string_int(cls, v: Any) -> Optional[int]:
        """Convert string integers to int."""
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return None
        return v if v is None else int(v)

    @field_validator("duration", mode="before")
    @classmethod
    def parse_string_float(cls, v: Any) -> Optional[float]:
        """Convert string floats to float."""
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return v if v is None else float(v)

    @field_validator("sample_rate", mode="before")
    @classmethod
    def ensure_string(cls, v: Any) -> str:
        """Ensure sample_rate is a string."""
        if isinstance(v, int):
            return str(v)
        return str(v)

    def get_sample_rate_as_int(self) -> Optional[int]:
        """
        Convert sample_rate string to integer.

        Returns:
            Sample rate as integer (e.g., 44100), or None if parsing fails.
        """
        try:
            return int(self.sample_rate)
        except (ValueError, TypeError):
            return None


class FFProbeMediaInfo(BaseModel):
    """Complete media information from ffprobe."""

    format: FFProbeFormat
    streams: List[dict] = Field(default_factory=list)

    @property
    def video_streams(self) -> List[FFProbeVideoStream]:
        """Extract and parse video streams."""
        video_streams = []
        for stream in self.streams:
            if stream.get("codec_type") == "video":
                try:
                    video_streams.append(FFProbeVideoStream.model_validate(stream))
                except Exception:
                    # Skip invalid video streams
                    continue
        return video_streams

    @property
    def audio_streams(self) -> List[FFProbeAudioStream]:
        """Extract and parse audio streams."""
        audio_streams = []
        for stream in self.streams:
            if stream.get("codec_type") == "audio":
                try:
                    audio_streams.append(FFProbeAudioStream.model_validate(stream))
                except Exception:
                    # Skip invalid audio streams
                    continue
        return audio_streams

    def get_primary_video_stream(self) -> Optional[FFProbeVideoStream]:
        """Get the first video stream (primary video track)."""
        video_streams = self.video_streams
        return video_streams[0] if video_streams else None

    def get_primary_audio_stream(self) -> Optional[FFProbeAudioStream]:
        """Get the first audio stream (primary audio track)."""
        audio_streams = self.audio_streams
        return audio_streams[0] if audio_streams else None
