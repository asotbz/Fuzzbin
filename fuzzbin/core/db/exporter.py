"""NFO file exporter for database records."""

import hashlib
from pathlib import Path
from typing import Optional

import structlog

from ...parsers.artist_parser import ArtistNFOParser
from ...parsers.models import ArtistNFO, MusicVideoNFO
from ...parsers.musicvideo_parser import MusicVideoNFOParser
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

    @staticmethod
    def _content_matches(path: Path, content: str) -> bool:
        """
        Check if existing file content matches new content using MD5 hash.

        Args:
            path: Path to existing file
            content: New content to compare

        Returns:
            True if file exists and content matches, False otherwise
        """
        if not path.exists():
            return False

        try:
            existing = path.read_text(encoding="utf-8")
            existing_hash = hashlib.md5(existing.encode("utf-8")).hexdigest()
            new_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
            return existing_hash == new_hash
        except Exception:
            return False

    async def _build_video_nfo(self, video_id: int) -> MusicVideoNFO:
        """
        Build MusicVideoNFO model from database record.

        Args:
            video_id: Video ID

        Returns:
            MusicVideoNFO model instance
        """
        # Get video record
        video = await self.repository.get_video_by_id(video_id)

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
        return MusicVideoNFO(
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

    async def generate_video_nfo_content(self, video_id: int) -> str:
        """
        Generate NFO XML content for a video without writing to disk.

        Args:
            video_id: Video ID

        Returns:
            XML string content for the NFO file
        """
        nfo = await self._build_video_nfo(video_id)
        return self.video_parser.to_xml_string(nfo)

    async def _build_artist_nfo(self, artist_id: int) -> ArtistNFO:
        """
        Build ArtistNFO model from database record.

        Args:
            artist_id: Artist ID

        Returns:
            ArtistNFO model instance
        """
        artist = await self.repository.get_artist_by_id(artist_id)
        return ArtistNFO(name=artist["name"])

    async def generate_artist_nfo_content(self, artist_id: int) -> str:
        """
        Generate NFO XML content for an artist without writing to disk.

        Args:
            artist_id: Artist ID

        Returns:
            XML string content for the NFO file
        """
        nfo = await self._build_artist_nfo(artist_id)
        return self.artist_parser.to_xml_string(nfo)

    async def export_video_to_nfo(
        self,
        video_id: int,
        nfo_path: Optional[Path] = None,
        skip_unchanged: bool = False,
    ) -> tuple[Path, bool]:
        """
        Export video record to NFO file.

        Args:
            video_id: Video ID
            nfo_path: Path for NFO file (uses video.nfo_file_path if not provided)
            skip_unchanged: If True, skip writing if content matches existing file

        Returns:
            Tuple of (path to NFO file, whether file was actually written)
            When skip_unchanged=True and content matches, returns (path, False)

        Raises:
            VideoNotFoundError: If video not found
            ValueError: If no nfo_path provided and video.nfo_file_path is None
        """
        # Determine output path
        if nfo_path is None:
            video = await self.repository.get_video_by_id(video_id)
            if video.get("nfo_file_path"):
                nfo_path = Path(video["nfo_file_path"])
            else:
                raise ValueError(f"No nfo_path provided and video {video_id} has no nfo_file_path")

        # Generate content
        content = await self.generate_video_nfo_content(video_id)

        # Check if content matches existing file
        if skip_unchanged and self._content_matches(nfo_path, content):
            logger.debug(
                "video_nfo_unchanged",
                video_id=video_id,
                nfo_path=str(nfo_path),
            )
            return nfo_path, False

        # Ensure parent directory exists
        nfo_path.parent.mkdir(parents=True, exist_ok=True)

        # Write NFO file
        with open(nfo_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(
            "video_nfo_exported",
            video_id=video_id,
            nfo_path=str(nfo_path),
        )

        return nfo_path, True

    async def export_artist_to_nfo(
        self,
        artist_id: int,
        nfo_path: Path,
        skip_unchanged: bool = False,
    ) -> tuple[Path, bool]:
        """
        Export artist record to NFO file.

        Args:
            artist_id: Artist ID
            nfo_path: Path for NFO file
            skip_unchanged: If True, skip writing if content matches existing file

        Returns:
            Tuple of (path to NFO file, whether file was actually written)
            When skip_unchanged=True and content matches, returns (path, False)

        Raises:
            ArtistNotFoundError: If artist not found
        """
        # Generate content
        content = await self.generate_artist_nfo_content(artist_id)

        # Check if content matches existing file
        if skip_unchanged and self._content_matches(nfo_path, content):
            logger.debug(
                "artist_nfo_unchanged",
                artist_id=artist_id,
                nfo_path=str(nfo_path),
            )
            return nfo_path, False

        # Ensure parent directory exists
        nfo_path.parent.mkdir(parents=True, exist_ok=True)

        # Write NFO file
        with open(nfo_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(
            "artist_nfo_exported",
            artist_id=artist_id,
            nfo_path=str(nfo_path),
        )

        return nfo_path, True
