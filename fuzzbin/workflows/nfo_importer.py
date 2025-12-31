"""NFO file importer workflow for importing music video metadata into the database."""

import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

from ..common.string_utils import normalize_genre
from ..core.db.repository import VideoRepository
from ..parsers.models import MusicVideoNFO
from ..parsers.musicvideo_parser import MusicVideoNFOParser
from .spotify_importer import ImportResult


logger = structlog.get_logger(__name__)

# Batch size for transaction chunking - limits concurrent API calls and enables partial progress recovery
BATCH_SIZE = 25

# Video file extensions to discover alongside NFO files
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}


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
        api_config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ImportResult, List[Tuple[int, Optional[Path]]]]:
        """
        Import all music video NFO files from a directory.

        Args:
            root_path: Root directory to scan for NFO files
            recursive: Scan subdirectories recursively (default: True)
            update_file_paths: Update nfo_file_path in database (default: True)
            api_config: Optional API configuration dict with 'imvdb' and 'discogs' keys
                        for enrichment during import

        Returns:
            Tuple of (ImportResult with statistics, List of (video_id, video_file_path) tuples)
            The list contains all successfully imported videos for VIDEO_POST_PROCESS queuing.

        Raises:
            ValueError: If root_path doesn't exist or isn't a directory

        Example:
            >>> result, imported_videos = await importer.import_from_directory(
            ...     root_path=Path("/media/music_videos"),
            ...     recursive=True,
            ...     api_config={"imvdb": imvdb_config, "discogs": discogs_config},
            ... )
            >>> print(f"Imported: {result.imported_count}/{result.total_files}")
            >>> for video_id, video_path in imported_videos:
            ...     if video_path:
            ...         # Queue VIDEO_POST_PROCESS job
            ...         pass
        """
        start_time = time.time()

        self.logger.info(
            "nfo_import_start",
            root_path=str(root_path),
            recursive=recursive,
            skip_existing=self.skip_existing,
            has_api_config=bool(api_config),
        )

        # Discover all .nfo files
        nfo_files = self._discover_nfo_files(root_path, recursive)

        # Filter to only musicvideo.nfo files
        musicvideo_nfos = await self._filter_musicvideo_nfos(nfo_files)

        # Import NFO files with batching and enrichment
        result, imported_videos = await self._import_nfo_files(
            musicvideo_nfos,
            update_file_paths,
            api_config=api_config,
        )

        result.duration_seconds = time.time() - start_time

        self.logger.info(
            "nfo_import_complete",
            root_path=str(root_path),
            imported=result.imported_count,
            skipped=result.skipped_count,
            failed=result.failed_count,
            videos_with_files=len([v for v in imported_videos if v[1] is not None]),
            duration=result.duration_seconds,
        )

        return result, imported_videos

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
        video_file_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Map MusicVideoNFO model to video database fields.

        Args:
            nfo: Parsed MusicVideoNFO model
            nfo_file_path: Optional path to NFO file (for storing in database)
            video_file_path: Optional path to discovered video file

        Returns:
            Dictionary suitable for repository.create_video()

        Note:
            - Maps all available fields from NFO to database schema
            - Normalizes genre to primary category using normalize_genre()
            - Sets download_source to "nfo_import"
            - Stores nfo_file_path and video_file_path if provided
            - Excludes tags and collections (database is source of truth)
        """
        # Normalize genre to primary category if present
        normalized_genre: Optional[str] = None
        if nfo.genre:
            original, normalized, is_mapped = normalize_genre(nfo.genre)
            normalized_genre = normalized
            if is_mapped and original != normalized:
                self.logger.debug(
                    "genre_normalized",
                    original=original,
                    normalized=normalized,
                )

        video_data = {
            "title": nfo.title,
            "artist": nfo.artist,
            "album": nfo.album,
            "year": nfo.year,
            "director": nfo.director,
            "genre": normalized_genre,
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

        # Add video file path if provided
        if video_file_path:
            video_data["video_file_path"] = str(video_file_path.resolve())

        return video_data

    def _discover_video_file(self, nfo_path: Path) -> Optional[Path]:
        """
        Discover video file matching the NFO file's base name.

        Looks for video files in the same directory as the NFO file with matching
        base names (e.g., 'Artist - Title.nfo' matches 'Artist - Title.mp4').

        Args:
            nfo_path: Path to the NFO file

        Returns:
            Path to video file if exactly one match found, None otherwise

        Note:
            - If multiple video files match the same base name, logs warning and returns None
            - Supported extensions: .mp4, .mkv, .avi, .mov, .webm, .m4v
        """
        nfo_dir = nfo_path.parent
        nfo_stem = nfo_path.stem  # Filename without extension

        matching_videos: List[Path] = []

        for video_ext in VIDEO_EXTENSIONS:
            video_path = nfo_dir / f"{nfo_stem}{video_ext}"
            if video_path.is_file():
                matching_videos.append(video_path)

        if len(matching_videos) == 0:
            self.logger.debug(
                "no_video_file_found",
                nfo_path=str(nfo_path),
                nfo_stem=nfo_stem,
            )
            return None

        if len(matching_videos) > 1:
            self.logger.warning(
                "multiple_video_files_found",
                nfo_path=str(nfo_path),
                nfo_stem=nfo_stem,
                video_files=[str(v) for v in matching_videos],
                message="Skipping video file discovery due to ambiguity",
            )
            return None

        video_path = matching_videos[0]
        self.logger.debug(
            "video_file_discovered",
            nfo_path=str(nfo_path),
            video_path=str(video_path),
        )
        return video_path

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
        video_file_path: Optional[Path] = None,
        api_config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[int], Optional[Path]]:
        """
        Import a single NFO file into the database with optional enrichment.

        Args:
            nfo: Parsed MusicVideoNFO model
            nfo_path: Optional NFO file path (for storing in database)
            video_file_path: Optional discovered video file path
            api_config: Optional API configuration for enrichment (imvdb, discogs)

        Returns:
            Tuple of (video_id, video_file_path) if successful, (None, None) if failed

        Note:
            - Attempts IMVDb enrichment for missing imvdb_video_id, year, director
            - Attempts Discogs enrichment for missing genre, album, label
            - Enrichment failures do not fail the import
        """
        # Map NFO to video data
        video_data = self._map_nfo_to_video_data(nfo, nfo_path, video_file_path)

        # Attempt IMVDb enrichment for missing fields
        imvdb_video_id: Optional[str] = None
        imvdb_video_data: Optional[Any] = None
        youtube_id: Optional[str] = None

        if api_config:
            imvdb_config = api_config.get("imvdb")
            if imvdb_config and nfo.artist and nfo.title:
                try:
                    from ..api.imvdb_client import IMVDbClient
                    from ..parsers.imvdb_parser import IMVDbParser

                    async with IMVDbClient.from_config(imvdb_config) as imvdb_client:
                        search_results = await imvdb_client.search_videos(
                            artist=nfo.artist,
                            track_title=nfo.title,
                            per_page=20,
                        )

                        if search_results.results:
                            try:
                                matched_video = IMVDbParser.find_best_video_match(
                                    results=search_results.results,
                                    artist=nfo.artist,
                                    title=nfo.title,
                                    threshold=0.8,
                                )
                                imvdb_video_id = str(matched_video.id)
                                imvdb_video_data = matched_video

                                # Extract fields from IMVDb if not in NFO
                                if not video_data.get("year") and matched_video.year:
                                    video_data["year"] = matched_video.year
                                if not video_data.get("director") and matched_video.directors:
                                    video_data["director"] = matched_video.directors[0].entity_name

                                # Extract YouTube ID from sources
                                if matched_video.sources:
                                    for source in matched_video.sources:
                                        if source.source == "youtube" and source.source_data:
                                            youtube_id = source.source_data
                                            break

                                video_data["imvdb_video_id"] = imvdb_video_id
                                if youtube_id:
                                    video_data["youtube_id"] = youtube_id

                                self.logger.info(
                                    "imvdb_enrichment_success",
                                    nfo_path=str(nfo_path) if nfo_path else None,
                                    imvdb_video_id=imvdb_video_id,
                                    title=nfo.title,
                                    artist=nfo.artist,
                                )
                            except Exception as match_error:
                                self.logger.debug(
                                    "imvdb_no_match_found",
                                    nfo_path=str(nfo_path) if nfo_path else None,
                                    title=nfo.title,
                                    artist=nfo.artist,
                                    error=str(match_error),
                                )
                except Exception as e:
                    self.logger.warning(
                        "imvdb_enrichment_error",
                        nfo_path=str(nfo_path) if nfo_path else None,
                        title=nfo.title,
                        artist=nfo.artist,
                        error=str(e),
                    )

            # Attempt Discogs enrichment for genre/album/label
            discogs_config = api_config.get("discogs")
            if discogs_config and nfo.artist:
                try:
                    from ..services.discogs_enrichment import DiscogsEnrichmentService

                    discogs_service = DiscogsEnrichmentService(
                        imvdb_config=imvdb_config,
                        discogs_config=discogs_config,
                    )

                    if imvdb_video_id:
                        # Use IMVDb video for enrichment
                        discogs_result = await discogs_service.enrich_from_imvdb_video(
                            imvdb_video_id=int(imvdb_video_id),
                            track_title=nfo.title,
                            artist_name=nfo.artist,
                        )
                    else:
                        # Fallback: search Discogs directly
                        discogs_result = await discogs_service.enrich_from_imvdb_video(
                            imvdb_video_id=0,  # Will trigger fallback search
                            track_title=nfo.title,
                            artist_name=nfo.artist,
                        )

                    # Apply Discogs enrichment for missing fields
                    if discogs_result:
                        if discogs_result.genre and not video_data.get("genre"):
                            _, normalized_genre, _ = normalize_genre(discogs_result.genre)
                            video_data["genre"] = normalized_genre
                        if discogs_result.album and not video_data.get("album"):
                            video_data["album"] = discogs_result.album
                        if discogs_result.label and not video_data.get("studio"):
                            video_data["studio"] = discogs_result.label
                        if discogs_result.year and not video_data.get("year"):
                            video_data["year"] = discogs_result.year
                        if discogs_result.discogs_artist_id:
                            video_data["discogs_artist_id"] = discogs_result.discogs_artist_id

                        self.logger.info(
                            "discogs_enrichment_success",
                            nfo_path=str(nfo_path) if nfo_path else None,
                            genre=discogs_result.genre,
                            album=discogs_result.album,
                            match_method=discogs_result.match_method,
                        )
                except Exception as e:
                    self.logger.warning(
                        "discogs_enrichment_error",
                        nfo_path=str(nfo_path) if nfo_path else None,
                        title=nfo.title,
                        artist=nfo.artist,
                        error=str(e),
                    )

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
            video_file_path=str(video_file_path) if video_file_path else None,
            title=nfo.title,
            artist=nfo.artist,
            featured_count=len(nfo.featured_artists),
            has_imvdb=bool(imvdb_video_id),
        )

        return video_id, video_file_path

    async def _import_nfo_files(
        self,
        nfo_files: List[Path],
        update_file_paths: bool,
        api_config: Optional[Dict[str, Any]] = None,
    ) -> Tuple[ImportResult, List[Tuple[int, Optional[Path]]]]:
        """
        Import list of NFO files into database in batches.

        Processes NFO files in batches of BATCH_SIZE (25) for:
        - Transaction chunking (partial progress survives crashes)
        - Manageable concurrency for API enrichment calls
        - Better progress visibility

        Args:
            nfo_files: List of musicvideo.nfo file paths
            update_file_paths: Whether to store NFO file paths in database
            api_config: Optional API configuration for enrichment

        Returns:
            Tuple of (ImportResult with statistics, List of (video_id, video_file_path) tuples)
        """
        result = ImportResult(
            playlist_id="nfo_import",
            playlist_name=f"NFO Import ({len(nfo_files)} files)",
            total_tracks=len(nfo_files),
        )

        # Collect imported videos for post-processing
        imported_videos: List[Tuple[int, Optional[Path]]] = []
        total_files = len(nfo_files)

        # Process in batches
        for batch_start in range(0, total_files, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_files)
            batch = nfo_files[batch_start:batch_end]

            self.logger.info(
                "processing_batch",
                batch_start=batch_start + 1,
                batch_end=batch_end,
                total=total_files,
                batch_size=len(batch),
            )

            # Each batch gets its own transaction for partial progress recovery
            async with self.repository.transaction():
                for batch_idx, nfo_path in enumerate(batch):
                    global_idx = batch_start + batch_idx + 1

                    # Report progress via callback if provided
                    if self.progress_callback:
                        self.progress_callback(global_idx, total_files, nfo_path.name)

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

                        # Discover companion video file
                        video_file_path = self._discover_video_file(nfo_path)

                        # Import video with enrichment
                        video_id, discovered_path = await self._import_single_nfo(
                            nfo=nfo,
                            nfo_path=nfo_path if update_file_paths else None,
                            video_file_path=video_file_path,
                            api_config=api_config,
                        )

                        if video_id is not None:
                            result.imported_count += 1
                            imported_videos.append((video_id, discovered_path))

                            # Log progress every 10 files
                            if global_idx % 10 == 0:
                                self.logger.info(
                                    "import_progress",
                                    processed=global_idx,
                                    total=total_files,
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
                                "name": (
                                    nfo.title
                                    if "nfo" in dir() and hasattr(nfo, "title")
                                    else "Unknown"
                                ),
                                "error": str(e),
                            }
                        )

            # Log batch completion
            self.logger.info(
                "batch_completed",
                batch_start=batch_start + 1,
                batch_end=batch_end,
                imported_in_batch=(
                    len(
                        [
                            v
                            for v in imported_videos
                            if v[0] and batch_start <= nfo_files.index(nfo_path) < batch_end
                        ]
                    )
                    if nfo_path
                    else 0
                ),
            )

        return result, imported_videos
