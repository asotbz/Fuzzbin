"""NFO file importer workflow for importing music video metadata into the database."""

import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import structlog

from ..core.db.repository import VideoRepository
from ..parsers.models import MusicVideoNFO
from ..parsers.musicvideo_parser import MusicVideoNFOParser
from .spotify_importer import ImportResult


logger = structlog.get_logger(__name__)


class NFOImporter:
    """
    Import music video metadata from NFO files into the video database.

    This workflow:
    1. Scans directory tree for .nfo files
    2. Identifies musicvideo.nfo files (vs artist.nfo) by XML root element
    3. Parses NFO metadata
    4. Maps NFO data to database schema
    5. Creates video and artist records
    6. Links artists to videos via junction table
    7. Reports import statistics

    Example:
        >>> import asyncio
        >>> from pathlib import Path
        >>> from fuzzbin.core.db.repository import VideoRepository
        >>> from fuzzbin.workflows.nfo_importer import NFOImporter
        >>>
        >>> async def main():
        ...     repository = await VideoRepository.from_config(config.database)
        ...
        ...     importer = NFOImporter(
        ...         video_repository=repository,
        ...         initial_status="discovered",
        ...         skip_existing=True,
        ...     )
        ...
        ...     result = await importer.import_from_directory(
        ...         root_path=Path("/media/music_videos"),
        ...         recursive=True,
        ...     )
        ...     print(f"Imported {result.imported_count} NFO files")
        ...
        ...     await repository.close()
        >>>
        >>> asyncio.run(main())
    """

    def __init__(
        self,
        video_repository: VideoRepository,
        initial_status: str = "discovered",
        skip_existing: bool = True,
        nfo_parser: Optional[MusicVideoNFOParser] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ):
        """
        Initialize NFO importer.

        Args:
            video_repository: Database repository for video CRUD operations
            initial_status: Status for newly imported videos (default: "discovered")
            skip_existing: Skip videos that already exist in database (default: True)
            nfo_parser: Optional custom parser (default: creates MusicVideoNFOParser())
            progress_callback: Optional callback for progress updates.
                Called with (processed_count, total_count, current_file_name)
                for real-time progress tracking in background tasks.
        """
        self.repository = video_repository
        self.initial_status = initial_status
        self.skip_existing = skip_existing
        self.parser = nfo_parser or MusicVideoNFOParser()
        self.progress_callback = progress_callback
        self.logger = structlog.get_logger(__name__)

    async def import_from_directory(
        self,
        root_path: Path,
        recursive: bool = True,
        update_file_paths: bool = True,
    ) -> ImportResult:
        """
        Import all music video NFO files from a directory.

        Args:
            root_path: Root directory to scan for NFO files
            recursive: Scan subdirectories recursively (default: True)
            update_file_paths: Update nfo_file_path in database (default: True)

        Returns:
            ImportResult with statistics about the import operation

        Raises:
            ValueError: If root_path doesn't exist or isn't a directory

        Example:
            >>> result = await importer.import_from_directory(
            ...     root_path=Path("/media/music_videos"),
            ...     recursive=True,
            ... )
            >>> print(f"Imported: {result.imported_count}/{result.total_files}")
        """
        start_time = time.time()

        self.logger.info(
            "nfo_import_start",
            root_path=str(root_path),
            recursive=recursive,
            skip_existing=self.skip_existing,
        )

        # Discover all .nfo files
        nfo_files = self._discover_nfo_files(root_path, recursive)

        # Filter to only musicvideo.nfo files
        musicvideo_nfos = await self._filter_musicvideo_nfos(nfo_files)

        # Import NFO files
        result = await self._import_nfo_files(musicvideo_nfos, update_file_paths)

        result.duration_seconds = time.time() - start_time

        self.logger.info(
            "nfo_import_complete",
            root_path=str(root_path),
            imported=result.imported_count,
            skipped=result.skipped_count,
            failed=result.failed_count,
            duration=result.duration_seconds,
        )

        return result

    def _discover_nfo_files(self, root_path: Path, recursive: bool) -> List[Path]:
        """
        Discover all .nfo files in directory tree.

        Args:
            root_path: Root directory to scan
            recursive: Scan subdirectories recursively

        Returns:
            List of .nfo file paths

        Raises:
            ValueError: If root_path doesn't exist or isn't a directory
        """
        if not root_path.exists():
            raise ValueError(f"Path does not exist: {root_path}")
        if not root_path.is_dir():
            raise ValueError(f"Path is not a directory: {root_path}")

        if recursive:
            nfo_files = list(root_path.rglob("*.nfo"))
        else:
            nfo_files = list(root_path.glob("*.nfo"))

        self.logger.info(
            "nfo_files_discovered",
            root_path=str(root_path),
            count=len(nfo_files),
            recursive=recursive,
        )

        return nfo_files

    def _identify_nfo_type(self, nfo_path: Path) -> Optional[str]:
        """
        Identify NFO file type by parsing root element.

        Args:
            nfo_path: Path to NFO file

        Returns:
            "musicvideo", "artist", or None if unrecognized/malformed

        Note:
            Returns None on parse errors (logged as debug, not error)
        """
        try:
            tree = ET.parse(nfo_path)
            root = tree.getroot()

            if root.tag in ("musicvideo", "artist"):
                return root.tag
            else:
                self.logger.debug(
                    "unrecognized_nfo_type",
                    nfo_path=str(nfo_path),
                    root_tag=root.tag,
                )
                return None
        except ET.ParseError as e:
            self.logger.debug(
                "nfo_parse_error_during_identification",
                nfo_path=str(nfo_path),
                error=str(e),
            )
            return None
        except Exception as e:
            self.logger.debug(
                "nfo_identification_error",
                nfo_path=str(nfo_path),
                error=str(e),
            )
            return None

    async def _filter_musicvideo_nfos(self, nfo_files: List[Path]) -> List[Path]:
        """
        Filter NFO files to only musicvideo.nfo files.

        Args:
            nfo_files: List of all .nfo file paths

        Returns:
            List of musicvideo.nfo file paths only
        """
        musicvideo_nfos = []
        artist_count = 0

        for nfo_file in nfo_files:
            nfo_type = self._identify_nfo_type(nfo_file)
            if nfo_type == "musicvideo":
                musicvideo_nfos.append(nfo_file)
            elif nfo_type == "artist":
                artist_count += 1

        self.logger.info(
            "nfo_files_filtered",
            total_files=len(nfo_files),
            musicvideo_count=len(musicvideo_nfos),
            artist_count=artist_count,
        )

        return musicvideo_nfos

    def _validate_critical_fields(self, nfo: MusicVideoNFO, nfo_path: Path) -> bool:
        """
        Validate that NFO has critical fields required for import.

        Args:
            nfo: Parsed MusicVideoNFO model
            nfo_path: Path to NFO file (for logging)

        Returns:
            True if valid, False if missing critical fields

        Note:
            Critical fields: title, artist
            Logs error if validation fails
        """
        if not nfo.title or not nfo.artist:
            self.logger.error(
                "nfo_missing_critical_fields",
                nfo_path=str(nfo_path),
                has_title=bool(nfo.title),
                has_artist=bool(nfo.artist),
            )
            return False

        return True

    def _map_nfo_to_video_data(
        self,
        nfo: MusicVideoNFO,
        nfo_file_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Map MusicVideoNFO model to video database fields.

        Args:
            nfo: Parsed MusicVideoNFO model
            nfo_file_path: Optional path to NFO file (for storing in database)

        Returns:
            Dictionary suitable for repository.create_video()

        Note:
            - Maps all available fields from NFO to database schema
            - Sets download_source to "nfo_import"
            - Stores nfo_file_path if provided
            - Excludes tags and collections (database is source of truth)
        """
        video_data = {
            "title": nfo.title,
            "artist": nfo.artist,
            "album": nfo.album,
            "year": nfo.year,
            "director": nfo.director,
            "genre": nfo.genre,
            "studio": nfo.studio,
            "status": self.initial_status,
            "download_source": "nfo_import",
        }
        # Note: tags and collections are intentionally excluded from import
        # The database is the source of truth for tags/collections,
        # which are written TO NFO files but not imported FROM them

        # Add NFO file path if provided
        if nfo_file_path:
            video_data["nfo_file_path"] = str(nfo_file_path.resolve())

        return video_data

    async def _check_video_exists(self, nfo: MusicVideoNFO) -> bool:
        """
        Check if video already exists in database.

        Queries by title + artist combination.

        Args:
            nfo: Parsed MusicVideoNFO model

        Returns:
            True if video exists, False otherwise
        """
        if not nfo.artist or not nfo.title:
            return False

        try:
            query = self.repository.query()
            query = query.where_title(nfo.title)
            query = query.where_artist(nfo.artist)

            results = await query.execute()
            return len(results) > 0

        except Exception as e:
            # If query fails, assume doesn't exist
            self.logger.warning(
                "video_exists_check_failed",
                title=nfo.title,
                artist=nfo.artist,
                error=str(e),
            )
            return False

    async def _import_single_nfo(
        self,
        nfo: MusicVideoNFO,
        nfo_path: Optional[Path],
    ) -> Optional[int]:
        """
        Import a single NFO file into the database.

        Args:
            nfo: Parsed MusicVideoNFO model
            nfo_path: Optional NFO file path (for storing in database)

        Returns:
            Video ID if successful, None if failed

        Raises:
            Exception: If import fails
        """
        # Map NFO to video data
        video_data = self._map_nfo_to_video_data(nfo, nfo_path)

        # Create video record
        video_id = await self.repository.create_video(**video_data)

        # Upsert primary artist and link
        if nfo.artist:
            artist_id = await self.repository.upsert_artist(name=nfo.artist)
            await self.repository.link_video_artist(
                video_id=video_id,
                artist_id=artist_id,
                role="primary",
                position=0,
            )

        # Upsert featured artists and link
        for position, featured_artist in enumerate(nfo.featured_artists, start=1):
            artist_id = await self.repository.upsert_artist(name=featured_artist)
            await self.repository.link_video_artist(
                video_id=video_id,
                artist_id=artist_id,
                role="featured",
                position=position,
            )

        self.logger.info(
            "nfo_imported",
            video_id=video_id,
            nfo_path=str(nfo_path) if nfo_path else None,
            title=nfo.title,
            artist=nfo.artist,
            featured_count=len(nfo.featured_artists),
        )

        return video_id

    async def _import_nfo_files(
        self,
        nfo_files: List[Path],
        update_file_paths: bool,
    ) -> ImportResult:
        """
        Import list of NFO files into database.

        Args:
            nfo_files: List of musicvideo.nfo file paths
            update_file_paths: Whether to store NFO file paths in database

        Returns:
            ImportResult with statistics
        """
        result = ImportResult(
            playlist_id="nfo_import",
            playlist_name=f"NFO Import ({len(nfo_files)} files)",
            total_tracks=len(nfo_files),
        )

        # Import each NFO within a single transaction
        async with self.repository.transaction():
            for idx, nfo_path in enumerate(nfo_files, start=1):
                # Report progress via callback if provided
                if self.progress_callback:
                    self.progress_callback(idx, len(nfo_files), nfo_path.name)

                try:
                    # Parse NFO file
                    nfo = self.parser.parse_file(nfo_path)

                    # Validate critical fields
                    if not self._validate_critical_fields(nfo, nfo_path):
                        result.failed_count += 1
                        result.failed_tracks.append(
                            {
                                "track_id": str(nfo_path),
                                "name": nfo.title or "Unknown",
                                "error": "Missing critical fields (title or artist)",
                            }
                        )
                        continue

                    # Check if exists
                    if self.skip_existing and await self._check_video_exists(nfo):
                        self.logger.debug(
                            "video_skipped_exists",
                            nfo_path=str(nfo_path),
                            title=nfo.title,
                            artist=nfo.artist,
                        )
                        result.skipped_count += 1
                        continue

                    # Import video
                    video_id = await self._import_single_nfo(
                        nfo=nfo,
                        nfo_path=nfo_path if update_file_paths else None,
                    )

                    if video_id is not None:
                        result.imported_count += 1

                        # Log progress every 10 files
                        if idx % 10 == 0:
                            self.logger.info(
                                "import_progress",
                                processed=idx,
                                total=len(nfo_files),
                                imported=result.imported_count,
                                skipped=result.skipped_count,
                                failed=result.failed_count,
                            )
                    else:
                        result.failed_count += 1

                except Exception as e:
                    self.logger.error(
                        "nfo_import_failed",
                        nfo_path=str(nfo_path),
                        error=str(e),
                    )
                    result.failed_count += 1
                    result.failed_tracks.append(
                        {
                            "track_id": str(nfo_path),
                            "name": nfo.title if hasattr(nfo, "title") else "Unknown",
                            "error": str(e),
                        }
                    )

        return result
