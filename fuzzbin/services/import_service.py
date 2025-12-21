"""Import service for unified import orchestration.

This service wraps existing workflow classes (NFOImporter, SpotifyPlaylistImporter)
and provides a unified interface for all import operations. It handles:
- NFO directory imports
- Spotify playlist imports
- YouTube search/download imports (future)
- Progress reporting via callbacks

Example:
    >>> from fuzzbin.services import ImportService
    >>> 
    >>> async def my_route(import_service: ImportService = Depends(get_import_service)):
    ...     result = await import_service.import_nfo_directory(
    ...         directory=Path("/media/videos"),
    ...         recursive=True,
    ...     )
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import structlog

from fuzzbin.core.db.repository import VideoRepository
from fuzzbin.workflows.nfo_importer import NFOImporter
from fuzzbin.workflows.spotify_importer import ImportResult, SpotifyPlaylistImporter

from .base import (
    BaseService,
    NotFoundError,
    ServiceCallback,
    ServiceError,
    ValidationError,
)

logger = structlog.get_logger(__name__)


# ==================== Data Classes ====================


@dataclass
class NFOImportResult:
    """Result of NFO directory import."""

    root_path: str
    total_files: int = 0
    imported_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    failed_files: List[Dict[str, str]] = field(default_factory=list)
    duration_seconds: float = 0.0

    @classmethod
    def from_workflow_result(cls, result: ImportResult, root_path: str) -> "NFOImportResult":
        """Convert from workflow ImportResult."""
        return cls(
            root_path=root_path,
            total_files=result.total_tracks,  # reused field
            imported_count=result.imported_count,
            skipped_count=result.skipped_count,
            failed_count=result.failed_count,
            failed_files=result.failed_tracks,  # reused field
            duration_seconds=result.duration_seconds,
        )


@dataclass
class SpotifyImportResult:
    """Result of Spotify playlist import."""

    playlist_id: str
    playlist_name: str
    total_tracks: int = 0
    imported_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    failed_tracks: List[Dict[str, str]] = field(default_factory=list)
    duration_seconds: float = 0.0

    @classmethod
    def from_workflow_result(cls, result: ImportResult) -> "SpotifyImportResult":
        """Convert from workflow ImportResult."""
        return cls(
            playlist_id=result.playlist_id,
            playlist_name=result.playlist_name,
            total_tracks=result.total_tracks,
            imported_count=result.imported_count,
            skipped_count=result.skipped_count,
            failed_count=result.failed_count,
            failed_tracks=result.failed_tracks,
            duration_seconds=result.duration_seconds,
        )


# ==================== Service ====================


class ImportService(BaseService):
    """
    Service for orchestrating import workflows.

    Wraps existing workflow classes to provide:
    - Unified interface for all import types
    - Consistent progress reporting via callbacks
    - Service-level error handling
    - Logging and monitoring

    The service doesn't replace the workflow classes but wraps them,
    allowing the workflow logic to remain encapsulated while providing
    a clean API for the web layer.
    """

    def __init__(
        self,
        repository: VideoRepository,
        callback: Optional[ServiceCallback] = None,
        spotify_client: Optional[Any] = None,
    ):
        """
        Initialize the import service.

        Args:
            repository: VideoRepository for database operations
            callback: Optional callback for progress/failure hooks
            spotify_client: Optional SpotifyClient for Spotify imports.
                           If not provided, must be passed to import_spotify_playlist.
        """
        super().__init__(repository, callback)
        self._spotify_client = spotify_client

    def _create_progress_callback(
        self,
    ) -> Callable[[int, int, str], None]:
        """
        Create a progress callback that bridges workflow callbacks to service callbacks.

        Returns:
            Callback function compatible with workflow classes
        """

        def callback(current: int, total: int, message: str) -> None:
            # Note: workflow callbacks are sync, but we want to report via async callback
            # For now, we just log - proper async bridging would require more infrastructure
            self.logger.debug(
                "import_progress",
                current=current,
                total=total,
                message=message,
            )

        return callback

    # ==================== NFO Import ====================

    async def import_nfo_directory(
        self,
        directory: Path,
        recursive: bool = True,
        skip_existing: bool = True,
        initial_status: str = "discovered",
        update_file_paths: bool = True,
    ) -> NFOImportResult:
        """
        Import music video metadata from NFO files in a directory.

        Wraps NFOImporter workflow with service-level error handling
        and progress reporting.

        Args:
            directory: Directory to scan for NFO files
            recursive: Scan subdirectories recursively (default: True)
            skip_existing: Skip videos that already exist (default: True)
            initial_status: Status for newly imported videos (default: "discovered")
            update_file_paths: Update file paths in database (default: True)

        Returns:
            NFOImportResult with import statistics

        Raises:
            ValidationError: If directory doesn't exist or isn't valid
            ServiceError: If import fails
        """
        # Validate directory
        if not directory.exists():
            raise ValidationError(
                f"Directory does not exist: {directory}",
                field="directory",
            )
        if not directory.is_dir():
            raise ValidationError(
                f"Path is not a directory: {directory}",
                field="directory",
            )

        self.logger.info(
            "nfo_import_starting",
            directory=str(directory),
            recursive=recursive,
            skip_existing=skip_existing,
        )

        try:
            # Create importer with progress callback
            importer = NFOImporter(
                video_repository=self.repository,
                initial_status=initial_status,
                skip_existing=skip_existing,
                progress_callback=self._create_progress_callback(),
            )

            # Run import
            result = await importer.import_from_directory(
                root_path=directory,
                recursive=recursive,
                update_file_paths=update_file_paths,
            )

            # Convert to service result
            service_result = NFOImportResult.from_workflow_result(
                result, str(directory)
            )

            # Report completion via callback
            await self._report_complete(service_result)

            self.logger.info(
                "nfo_import_complete",
                directory=str(directory),
                imported=service_result.imported_count,
                skipped=service_result.skipped_count,
                failed=service_result.failed_count,
                duration=service_result.duration_seconds,
            )

            return service_result

        except ValueError as e:
            # NFOImporter raises ValueError for path issues
            raise ValidationError(str(e), field="directory") from e
        except Exception as e:
            self.logger.error(
                "nfo_import_failed",
                directory=str(directory),
                error=str(e),
            )
            await self._report_failure(e, {"directory": str(directory)})
            raise ServiceError(f"NFO import failed: {e}") from e

    # ==================== Spotify Import ====================

    async def import_spotify_playlist(
        self,
        playlist_id: str,
        skip_existing: bool = True,
        initial_status: str = "discovered",
        spotify_client: Optional[Any] = None,
    ) -> SpotifyImportResult:
        """
        Import tracks from a Spotify playlist.

        Wraps SpotifyPlaylistImporter workflow with service-level error handling
        and progress reporting.

        Args:
            playlist_id: Spotify playlist ID (e.g., "37i9dQZF1DXcBWIGoYBM5M")
            skip_existing: Skip tracks that already exist (default: True)
            initial_status: Status for newly imported tracks (default: "discovered")
            spotify_client: SpotifyClient instance (uses service default if not provided)

        Returns:
            SpotifyImportResult with import statistics

        Raises:
            ValidationError: If playlist_id is invalid or no Spotify client
            ServiceError: If import fails
        """
        # Get Spotify client
        client = spotify_client or self._spotify_client
        if client is None:
            raise ValidationError(
                "Spotify client is required for playlist import",
                field="spotify_client",
            )

        if not playlist_id:
            raise ValidationError(
                "Playlist ID is required",
                field="playlist_id",
            )

        self.logger.info(
            "spotify_import_starting",
            playlist_id=playlist_id,
            skip_existing=skip_existing,
        )

        try:
            # Create importer with progress callback
            importer = SpotifyPlaylistImporter(
                spotify_client=client,
                video_repository=self.repository,
                initial_status=initial_status,
                skip_existing=skip_existing,
                progress_callback=self._create_progress_callback(),
            )

            # Run import
            result = await importer.import_playlist(playlist_id)

            # Convert to service result
            service_result = SpotifyImportResult.from_workflow_result(result)

            # Report completion via callback
            await self._report_complete(service_result)

            self.logger.info(
                "spotify_import_complete",
                playlist_id=playlist_id,
                playlist_name=service_result.playlist_name,
                imported=service_result.imported_count,
                skipped=service_result.skipped_count,
                failed=service_result.failed_count,
                duration=service_result.duration_seconds,
            )

            return service_result

        except Exception as e:
            self.logger.error(
                "spotify_import_failed",
                playlist_id=playlist_id,
                error=str(e),
            )
            await self._report_failure(e, {"playlist_id": playlist_id})
            raise ServiceError(f"Spotify import failed: {e}") from e

    # ==================== YouTube Import (Future) ====================

    async def import_youtube_search(
        self,
        query: str,
        max_results: int = 10,
        download: bool = False,
        initial_status: str = "discovered",
    ) -> Dict[str, Any]:
        """
        Import videos from YouTube search results.

        Placeholder for future implementation.

        Args:
            query: Search query
            max_results: Maximum results to import
            download: Whether to download video files
            initial_status: Status for imported videos

        Returns:
            Import result dict

        Raises:
            NotImplementedError: This feature is not yet implemented
        """
        raise NotImplementedError(
            "YouTube import is not yet implemented. "
            "Use the yt-dlp client directly for now."
        )

    # ==================== Batch Import ====================

    async def import_multiple_nfo_directories(
        self,
        directories: List[Path],
        recursive: bool = True,
        skip_existing: bool = True,
        initial_status: str = "discovered",
    ) -> List[NFOImportResult]:
        """
        Import NFO files from multiple directories.

        Args:
            directories: List of directories to scan
            recursive: Scan subdirectories recursively
            skip_existing: Skip existing videos
            initial_status: Status for new videos

        Returns:
            List of NFOImportResult, one per directory
        """
        results = []
        total_dirs = len(directories)

        for i, directory in enumerate(directories, start=1):
            await self._report_progress(
                i, total_dirs, f"Importing from {directory.name}"
            )

            try:
                result = await self.import_nfo_directory(
                    directory=directory,
                    recursive=recursive,
                    skip_existing=skip_existing,
                    initial_status=initial_status,
                )
                results.append(result)
            except Exception as e:
                self.logger.warning(
                    "batch_nfo_import_directory_failed",
                    directory=str(directory),
                    error=str(e),
                )
                # Continue with next directory
                results.append(
                    NFOImportResult(
                        root_path=str(directory),
                        failed_count=1,
                        failed_files=[{"path": str(directory), "error": str(e)}],
                    )
                )

        return results
