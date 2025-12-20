"""NFO file exporter for database records."""

from pathlib import Path
from typing import Optional

import structlog

from ...parsers.artist_parser import ArtistNFOParser
from ...parsers.models import ArtistNFO, MusicVideoNFO
from ...parsers.musicvideo_parser import MusicVideoNFOParser
from .exceptions import ArtistNotFoundError, VideoNotFoundError
from .repository import VideoRepository

logger = structlog.get_logger(__name__)


class NFOExporter:
    """Exports database records to NFO files."""

    def __init__(self, repository: VideoRepository):
        """
        Initialize NFO exporter.

        Args:
            repository: VideoRepository instance
        """
        self.repository = repository
        self.video_parser = MusicVideoNFOParser()
        self.artist_parser = ArtistNFOParser()

    async def export_video_to_nfo(
        self,
        video_id: int,
        nfo_path: Optional[Path] = None,
    ) -> Path:
        """
        Export video record to NFO file.

        Args:
            video_id: Video ID
            nfo_path: Path for NFO file (uses video.nfo_file_path if not provided)

        Returns:
            Path to created NFO file

        Raises:
            VideoNotFoundError: If video not found
            ValueError: If no nfo_path provided and video.nfo_file_path is None
        """
        # Get video record
        video = await self.repository.get_video_by_id(video_id)

        # Determine output path
        if nfo_path is None:
            if video.get("nfo_file_path"):
                nfo_path = Path(video["nfo_file_path"])
            else:
                raise ValueError(f"No nfo_path provided and video {video_id} has no nfo_file_path")

        # Get video artists
        artists = await self.repository.get_video_artists(video_id)
        primary_artists = [a for a in artists if a["role"] == "primary"]
        featured_artists = [a for a in artists if a["role"] == "featured"]

        # Build primary artist name (use first primary artist or video.artist field)
        if primary_artists:
            artist_name = primary_artists[0]["name"]
        else:
            artist_name = video.get("artist", "")

        # Build featured artists list
        featured_artist_names = [a["name"] for a in featured_artists]

        # Get video tags from database
        video_tags = await self.repository.get_video_tags(video_id)
        tag_names = [tag["name"] for tag in video_tags]

        # Create MusicVideoNFO model
        nfo = MusicVideoNFO(
            title=video["title"],
            album=video.get("album"),
            studio=video.get("studio"),
            year=video.get("year"),
            director=video.get("director"),
            genre=video.get("genre"),
            artist=artist_name,
            featured_artists=featured_artist_names,
            tags=tag_names,
        )

        # Ensure parent directory exists
        nfo_path.parent.mkdir(parents=True, exist_ok=True)

        # Write NFO file
        self.video_parser.write_file(nfo, nfo_path)

        logger.info(
            "video_nfo_exported",
            video_id=video_id,
            nfo_path=str(nfo_path),
        )

        return nfo_path

    async def export_artist_to_nfo(
        self,
        artist_id: int,
        nfo_path: Path,
    ) -> Path:
        """
        Export artist record to NFO file.

        Args:
            artist_id: Artist ID
            nfo_path: Path for NFO file

        Returns:
            Path to created NFO file

        Raises:
            ArtistNotFoundError: If artist not found
        """
        # Get artist record
        artist = await self.repository.get_artist_by_id(artist_id)

        # Create ArtistNFO model
        nfo = ArtistNFO(
            name=artist["name"],
        )

        # Ensure parent directory exists
        nfo_path.parent.mkdir(parents=True, exist_ok=True)

        # Write NFO file
        self.artist_parser.write(nfo, nfo_path)

        logger.info(
            "artist_nfo_exported",
            artist_id=artist_id,
            nfo_path=str(nfo_path),
        )

        return nfo_path

    async def export_all_videos(
        self,
        output_dir: Path,
        filename_pattern: str = "{artist} - {title}.nfo",
    ) -> int:
        """
        Export all videos to NFO files in output directory.

        Args:
            output_dir: Directory for NFO files
            filename_pattern: Filename pattern with {artist}, {title} placeholders

        Returns:
            Number of NFO files exported

        Note:
            This method is not currently used but provided for bulk export capability.
        """
        # Get all videos
        videos = await self.repository.query().execute()

        output_dir.mkdir(parents=True, exist_ok=True)
        exported_count = 0

        for video in videos:
            try:
                # Build filename from pattern
                filename = filename_pattern.format(
                    artist=video.get("artist", "Unknown"),
                    title=video["title"],
                )
                # Sanitize filename
                filename = "".join(c for c in filename if c.isalnum() or c in " -_.")
                nfo_path = output_dir / filename

                await self.export_video_to_nfo(video["id"], nfo_path)
                exported_count += 1

            except Exception as e:
                logger.error(
                    "video_export_failed",
                    video_id=video["id"],
                    error=str(e),
                )

        logger.info(
            "bulk_export_complete",
            total=len(videos),
            exported=exported_count,
            output_dir=str(output_dir),
        )

        return exported_count
