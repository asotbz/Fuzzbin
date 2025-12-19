"""Parser for ffprobe JSON output."""

from typing import Any, Dict, Optional
import structlog

from .ffprobe_models import FFProbeMediaInfo, FFProbeVideoStream, FFProbeAudioStream

logger = structlog.get_logger(__name__)


class FFProbeParser:
    """Parser for ffprobe JSON output."""

    @staticmethod
    def parse_media_info(data: Dict[str, Any]) -> FFProbeMediaInfo:
        """
        Parse ffprobe JSON output into structured model.

        Args:
            data: Raw JSON dictionary from ffprobe output

        Returns:
            FFProbeMediaInfo object with parsed format and streams

        Raises:
            ValueError: If data is invalid or missing required fields

        Example:
            >>> data = {
            ...     "format": {"filename": "video.mp4", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            ...     "streams": [{"codec_type": "video", "codec_name": "h264", ...}]
            ... }
            >>> media_info = FFProbeParser.parse_media_info(data)
        """
        try:
            return FFProbeMediaInfo.model_validate(data)
        except Exception as e:
            logger.error(
                "ffprobe_parse_failed",
                error=str(e),
                has_format="format" in data,
                has_streams="streams" in data,
            )
            raise ValueError(f"Failed to parse ffprobe output: {e}") from e

    @staticmethod
    def extract_video_metadata(media_info: FFProbeMediaInfo) -> Dict[str, Any]:
        """
        Extract video metadata suitable for database storage.

        Extracts metadata from the primary video and audio streams,
        converting to flat dictionary matching database column names.

        Args:
            media_info: Parsed FFProbeMediaInfo object

        Returns:
            Dictionary with keys: duration, width, height, video_codec,
            audio_codec, container_format, bitrate, frame_rate,
            audio_channels, audio_sample_rate, aspect_ratio, file_size

        Example:
            >>> metadata = FFProbeParser.extract_video_metadata(media_info)
            >>> print(metadata["width"], metadata["height"])
            1920 1080
        """
        result: Dict[str, Any] = {}

        # Format-level metadata
        fmt = media_info.format
        result["duration"] = fmt.duration
        result["container_format"] = fmt.format_name
        result["bitrate"] = fmt.bit_rate
        result["file_size"] = fmt.size

        # Primary video stream metadata
        video_stream = media_info.get_primary_video_stream()
        if video_stream:
            result["width"] = video_stream.width
            result["height"] = video_stream.height
            result["video_codec"] = video_stream.codec_name
            result["aspect_ratio"] = video_stream.display_aspect_ratio
            result["frame_rate"] = video_stream.get_frame_rate_as_float()
        else:
            result["width"] = None
            result["height"] = None
            result["video_codec"] = None
            result["aspect_ratio"] = None
            result["frame_rate"] = None

        # Primary audio stream metadata
        audio_stream = media_info.get_primary_audio_stream()
        if audio_stream:
            result["audio_codec"] = audio_stream.codec_name
            result["audio_channels"] = audio_stream.channels
            result["audio_sample_rate"] = audio_stream.get_sample_rate_as_int()
        else:
            result["audio_codec"] = None
            result["audio_channels"] = None
            result["audio_sample_rate"] = None

        logger.debug(
            "video_metadata_extracted",
            duration=result["duration"],
            resolution=f"{result['width']}x{result['height']}" if result["width"] else None,
            video_codec=result["video_codec"],
            audio_codec=result["audio_codec"],
        )

        return result
