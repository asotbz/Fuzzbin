"""Video service for CRUD operations, file management, and metadata enrichment.

This service consolidates business logic from routes/videos.py and routes/files.py
into a single cohesive class. It orchestrates:
- Video CRUD with relationship loading
- File operations (organize, delete, restore)
- Thumbnail generation
- Duplicate detection
- Existence checks

Example:
    >>> from fuzzbin.services import VideoService
    >>>
    >>> async def my_route(video_service: VideoService = Depends(get_video_service)):
    ...     video = await video_service.get_with_relationships(video_id)
    ...     await video_service.organize(video_id, dry_run=False)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from fuzzbin.core.db.repository import VideoRepository
from fuzzbin.core.file_manager import (
    DuplicateCandidate,
    FileManager,
    FileManagerError,
    FileNotFoundError as FMFileNotFoundError,
    FileExistsError as FMFileExistsError,
    HashMismatchError,
    LibraryReport,
    RollbackError,
)
from fuzzbin.parsers.models import MusicVideoNFO

from .base import (
    BaseService,
    ConflictError,
    NotFoundError,
    ServiceCallback,
    ServiceError,
    ValidationError,
    cached_async,
)

logger = structlog.get_logger(__name__)


# ==================== Data Classes ====================


@dataclass
class VideoWithRelationships:
    """Video record with fully loaded relationships."""

    id: int
    data: Dict[str, Any]
    artists: List[Dict[str, Any]]
    collections: List[Dict[str, Any]]
    tags: List[Dict[str, Any]]

    @property
    def title(self) -> Optional[str]:
        return self.data.get("title")

    @property
    def artist(self) -> Optional[str]:
        return self.data.get("artist")

    @property
    def video_file_path(self) -> Optional[str]:
        return self.data.get("video_file_path")

    @property
    def nfo_file_path(self) -> Optional[str]:
        return self.data.get("nfo_file_path")


@dataclass
class OrganizeResult:
    """Result of a video organize operation."""

    video_id: int
    source_video_path: Optional[str]
    target_video_path: str
    target_nfo_path: str
    status: str  # 'moved', 'already_organized', or 'dry_run'
    dry_run: bool


@dataclass
class DeleteResult:
    """Result of a video delete operation."""

    video_id: int
    deleted: bool
    hard_delete: bool
    trash_path: Optional[str] = None


@dataclass
class RestoreResult:
    """Result of a video restore operation."""

    video_id: int
    restored: bool
    restored_path: str


@dataclass
class DuplicatesResult:
    """Result of duplicate detection."""

    video_id: int
    duplicates: List[DuplicateCandidate]
    total: int


@dataclass
class ResolveResult:
    """Result of duplicate resolution."""

    kept_video_id: int
    removed_count: int
    removed_video_ids: List[int]


# ==================== Service ====================


class VideoService(BaseService):
    """
    Service for video lifecycle management.

    Consolidates business logic from API routes into a testable service:
    - CRUD operations with automatic relationship loading
    - File operations (organize, delete, restore) via FileManager
    - Thumbnail generation
    - Duplicate detection and resolution
    - Video existence checks for imports

    All methods raise service-specific exceptions (NotFoundError, ConflictError, etc.)
    that can be mapped to HTTP status codes by the API layer.
    """

    def __init__(
        self,
        repository: VideoRepository,
        file_manager: Optional[FileManager] = None,
        callback: Optional[ServiceCallback] = None,
    ):
        """
        Initialize the video service.

        Args:
            repository: VideoRepository for database operations
            file_manager: Optional FileManager for file operations.
                          If not provided, will be created lazily from config.
            callback: Optional callback for progress/failure hooks
        """
        super().__init__(repository, callback)
        self._file_manager = file_manager
        self._file_manager_initialized = file_manager is not None

    async def _get_file_manager(self) -> FileManager:
        """
        Get or create FileManager instance.

        Lazily initializes FileManager from config if not provided at construction.
        """
        if not self._file_manager_initialized:
            config = self._get_config()
            library_dir = self._get_library_dir()
            config_dir = self._get_config_dir()
            self._file_manager = FileManager(
                config=config.trash,
                library_dir=library_dir,
                config_dir=config_dir,
                organizer_config=config.organizer,
                thumbnail_config=config.thumbnail,
            )
            self._file_manager_initialized = True
        return self._file_manager

    # ==================== CRUD Operations ====================

    async def get_by_id(
        self,
        video_id: int,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        """
        Get a video by ID.

        Args:
            video_id: Video ID
            include_deleted: Include soft-deleted videos

        Returns:
            Video record as dict

        Raises:
            NotFoundError: If video not found
        """
        try:
            video = await self.repository.get_video_by_id(video_id, include_deleted=include_deleted)
            return video
        except Exception as e:
            raise NotFoundError(
                f"Video not found: {video_id}",
                resource_type="video",
                resource_id=video_id,
            ) from e

    async def get_with_relationships(
        self,
        video_id: int,
        include_deleted: bool = False,
    ) -> VideoWithRelationships:
        """
        Get a video with all relationships loaded.

        Consolidates the repeated pattern of loading artists, collections,
        and tags separately after fetching a video.

        Args:
            video_id: Video ID
            include_deleted: Include soft-deleted videos

        Returns:
            VideoWithRelationships with artists, collections, tags loaded

        Raises:
            NotFoundError: If video not found
        """
        video = await self.get_by_id(video_id, include_deleted=include_deleted)
        artists = await self.repository.get_video_artists(video_id)
        collections = await self.repository.get_video_collections(video_id)
        tags = await self.repository.get_video_tags(video_id)

        return VideoWithRelationships(
            id=video_id,
            data=video,
            artists=artists,
            collections=collections,
            tags=tags,
        )

    async def create(
        self,
        title: str,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        year: Optional[int] = None,
        director: Optional[str] = None,
        genre: Optional[str] = None,
        studio: Optional[str] = None,
        status: str = "discovered",
        video_file_path: Optional[str] = None,
        nfo_file_path: Optional[str] = None,
        **kwargs,
    ) -> VideoWithRelationships:
        """
        Create a new video record.

        Args:
            title: Video title (required)
            artist: Primary artist name
            album: Album name
            year: Release year
            director: Director name
            genre: Genre
            studio: Studio name
            status: Initial status (default: "discovered")
            video_file_path: Path to video file
            nfo_file_path: Path to NFO file
            **kwargs: Additional video fields

        Returns:
            Created video with relationships

        Raises:
            ValidationError: If required fields are missing
        """
        if not title:
            raise ValidationError("Title is required", field="title")

        # Create video
        video_id = await self.repository.create_video(
            title=title,
            artist=artist,
            album=album,
            year=year,
            director=director,
            genre=genre,
            studio=studio,
            status=status,
            **kwargs,
        )

        # Update file paths if provided
        if video_file_path or nfo_file_path:
            await self.repository.update_video(
                video_id,
                video_file_path=video_file_path,
                nfo_file_path=nfo_file_path,
            )

        # Auto-add decade tag if year provided and auto_decade enabled
        if year:
            config = self._get_config()
            if config.tags.auto_decade.enabled:
                await self.repository.auto_add_decade_tag(
                    video_id, year, tag_format=config.tags.auto_decade.format
                )

        self.logger.info("video_created", video_id=video_id, title=title)
        return await self.get_with_relationships(video_id)

    async def create_with_artists(
        self,
        title: str,
        artists: List[Dict[str, Any]],
        **kwargs,
    ) -> VideoWithRelationships:
        """
        Create a video and link artists in a single transaction.

        Consolidates the common pattern of creating a video and then
        linking multiple artists.

        Args:
            title: Video title
            artists: List of artist dicts with keys:
                     - name (required)
                     - role (optional, default: "artist")
                     - position (optional, default: 0)
            **kwargs: Additional video fields

        Returns:
            Created video with relationships

        Raises:
            ValidationError: If title missing or artists invalid
        """
        if not title:
            raise ValidationError("Title is required", field="title")

        async with self.repository.transaction():
            # Create video
            video_id = await self.repository.create_video(title=title, **kwargs)

            # Link artists
            for i, artist_data in enumerate(artists):
                name = artist_data.get("name")
                if not name:
                    continue

                role = artist_data.get("role", "artist")
                position = artist_data.get("position", i)

                artist_id = await self.repository.upsert_artist(name=name)
                await self.repository.link_video_artist(
                    video_id=video_id,
                    artist_id=artist_id,
                    role=role,
                    position=position,
                )

        self.logger.info(
            "video_created_with_artists",
            video_id=video_id,
            title=title,
            artist_count=len(artists),
        )
        return await self.get_with_relationships(video_id)

    async def update(
        self,
        video_id: int,
        **kwargs,
    ) -> VideoWithRelationships:
        """
        Update a video's metadata.

        Args:
            video_id: Video ID
            **kwargs: Fields to update

        Returns:
            Updated video with relationships

        Raises:
            NotFoundError: If video not found
        """
        # Verify exists
        await self.get_by_id(video_id)

        # Update if there are changes
        if kwargs:
            await self.repository.update_video(video_id, **kwargs)
            self.logger.info("video_updated", video_id=video_id, fields=list(kwargs.keys()))

            # Emit WebSocket event for real-time UI updates
            from fuzzbin.core.event_bus import get_event_bus
            import time

            try:
                event_bus = get_event_bus()
                # Include timestamp if thumbnail-related fields changed
                thumbnail_related = {"thumbnail", "width", "height", "duration", "file_path"}
                thumbnail_ts = int(time.time()) if thumbnail_related & set(kwargs.keys()) else None
                await event_bus.emit_video_updated(
                    video_id=video_id,
                    fields_changed=list(kwargs.keys()),
                    thumbnail_timestamp=thumbnail_ts,
                )
            except RuntimeError:
                pass  # Event bus not initialized (tests)

            # Auto-add decade tag if year was updated and auto_decade enabled
            if "year" in kwargs and kwargs["year"]:
                config = self._get_config()
                if config.tags.auto_decade.enabled:
                    await self.repository.auto_add_decade_tag(
                        video_id, kwargs["year"], tag_format=config.tags.auto_decade.format
                    )

        return await self.get_with_relationships(video_id)

    async def update_status(
        self,
        video_id: int,
        new_status: str,
        reason: Optional[str] = None,
        changed_by: str = "service",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> VideoWithRelationships:
        """
        Update a video's status with tracking.

        Args:
            video_id: Video ID
            new_status: New status value
            reason: Optional reason for change
            changed_by: Who/what made the change
            metadata: Optional additional metadata

        Returns:
            Updated video with relationships

        Raises:
            NotFoundError: If video not found
        """
        await self.get_by_id(video_id)

        await self.repository.update_status(
            video_id=video_id,
            new_status=new_status,
            reason=reason,
            changed_by=changed_by,
            metadata=metadata,
        )

        self.logger.info(
            "video_status_updated",
            video_id=video_id,
            new_status=new_status,
            reason=reason,
        )
        return await self.get_with_relationships(video_id)

    async def delete(self, video_id: int) -> None:
        """
        Soft delete a video (database record only, not files).

        Args:
            video_id: Video ID

        Raises:
            NotFoundError: If video not found
        """
        await self.get_by_id(video_id)
        await self.repository.delete_video(video_id)
        self.logger.info("video_soft_deleted", video_id=video_id)

    async def restore(self, video_id: int) -> VideoWithRelationships:
        """
        Restore a soft-deleted video (database record only).

        Args:
            video_id: Video ID

        Returns:
            Restored video with relationships

        Raises:
            NotFoundError: If video not found
        """
        await self.get_by_id(video_id, include_deleted=True)
        await self.repository.restore_video(video_id)
        self.logger.info("video_restored", video_id=video_id)
        return await self.get_with_relationships(video_id)

    async def hard_delete(self, video_id: int) -> None:
        """
        Permanently delete a video (database record only, not files).

        Use delete_files() for file deletion.

        Args:
            video_id: Video ID

        Raises:
            NotFoundError: If video not found
        """
        await self.get_by_id(video_id, include_deleted=True)
        await self.repository.hard_delete_video(video_id)
        self.logger.info("video_hard_deleted", video_id=video_id)

    # ==================== Existence Checks ====================

    async def exists(
        self,
        title: str,
        artist: Optional[str] = None,
    ) -> bool:
        """
        Check if a video with given title/artist already exists.

        Consolidates the duplicate existence check pattern used in importers.

        Args:
            title: Video title
            artist: Optional artist name

        Returns:
            True if a matching video exists
        """
        query = self.repository.query()
        query = query.where_title(title)
        if artist:
            query = query.where_artist(artist)
        results = await query.execute()
        return len(results) > 0

    async def find_by_external_id(
        self,
        imvdb_video_id: Optional[str] = None,
        youtube_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a video by external service ID.

        Args:
            imvdb_video_id: IMVDb video ID
            youtube_id: YouTube video ID

        Returns:
            Video record if found, None otherwise
        """
        query = self.repository.query()

        if imvdb_video_id:
            query = query.where_imvdb_id(imvdb_video_id)
        elif youtube_id:
            query = query.where_youtube_id(youtube_id)
        else:
            return None

        results = await query.execute()
        return results[0] if results else None

    # ==================== File Operations ====================

    def _nfo_from_video(self, video: Dict[str, Any]) -> MusicVideoNFO:
        """Create MusicVideoNFO from video database record."""
        return MusicVideoNFO(
            title=video.get("title", ""),
            artist=video.get("artist"),
            album=video.get("album"),
            year=video.get("year"),
            director=video.get("director"),
            genre=video.get("genre"),
            studio=video.get("studio"),
        )

    async def organize(
        self,
        video_id: int,
        dry_run: bool = False,
    ) -> OrganizeResult:
        """
        Organize a video's files using configured path pattern.

        Moves video file (and NFO) to structured location based on metadata.

        Args:
            video_id: Video ID
            dry_run: If True, return target paths without moving files

        Returns:
            OrganizeResult with source/target paths and status

        Raises:
            NotFoundError: If video not found
            ConflictError: If target path already exists
            ServiceError: If file operation fails
        """
        video = await self.get_by_id(video_id)
        file_manager = await self._get_file_manager()
        nfo_data = self._nfo_from_video(video)

        try:
            target_paths = await file_manager.organize_video(
                video_id=video_id,
                repository=self.repository,
                nfo_data=nfo_data,
                dry_run=dry_run,
            )

            current_path = video.get("video_file_path")
            if str(target_paths.video_path) == current_path:
                status = "already_organized"
            elif dry_run:
                status = "dry_run"
            else:
                status = "moved"

            self.logger.info(
                "video_organized",
                video_id=video_id,
                status=status,
                target=str(target_paths.video_path),
            )

            return OrganizeResult(
                video_id=video_id,
                source_video_path=current_path,
                target_video_path=str(target_paths.video_path),
                target_nfo_path=str(target_paths.nfo_path),
                status=status,
                dry_run=dry_run,
            )

        except FMFileExistsError as e:
            raise ConflictError(
                f"Target file already exists: {e.path}",
                conflicting_id=video_id,
                path=str(e.path),
            ) from e
        except FMFileNotFoundError as e:
            raise NotFoundError(
                f"Source file not found: {e.path}",
                resource_type="file",
                resource_id=str(e.path),
            ) from e
        except HashMismatchError as e:
            raise ServiceError(
                f"File integrity check failed: {e}",
                details={"expected": e.expected_hash, "actual": e.actual_hash},
            ) from e
        except RollbackError as e:
            self.logger.error(
                "organize_rollback_failed",
                video_id=video_id,
                error=str(e),
                original_error=str(e.original_error),
            )
            raise ServiceError(
                f"File operation failed and rollback failed: {e}",
                details={"original_error": str(e.original_error)},
            ) from e
        except FileManagerError as e:
            raise ServiceError(f"File operation failed: {e}") from e

    async def delete_files(
        self,
        video_id: int,
        hard_delete: bool = False,
    ) -> DeleteResult:
        """
        Delete a video's files (soft or hard delete).

        Args:
            video_id: Video ID
            hard_delete: If True, permanently delete. If False, move to trash.

        Returns:
            DeleteResult with deletion status

        Raises:
            NotFoundError: If video or file not found
            ValidationError: If video has no file path
            ServiceError: If delete operation fails
        """
        video = await self.get_by_id(video_id, include_deleted=True)
        video_path = video.get("video_file_path")
        nfo_path = video.get("nfo_file_path")

        if not video_path:
            raise ValidationError("Video has no file path", field="video_file_path")

        file_manager = await self._get_file_manager()

        try:
            if hard_delete:
                await file_manager.hard_delete(
                    video_id=video_id,
                    video_path=Path(video_path),
                    repository=self.repository,
                    nfo_path=Path(nfo_path) if nfo_path else None,
                )
                self.logger.info("video_files_hard_deleted", video_id=video_id)
                return DeleteResult(
                    video_id=video_id,
                    deleted=True,
                    hard_delete=True,
                    trash_path=None,
                )
            else:
                trash_path = await file_manager.soft_delete(
                    video_id=video_id,
                    video_path=Path(video_path),
                    repository=self.repository,
                    nfo_path=Path(nfo_path) if nfo_path else None,
                )
                self.logger.info(
                    "video_files_soft_deleted",
                    video_id=video_id,
                    trash_path=str(trash_path),
                )
                return DeleteResult(
                    video_id=video_id,
                    deleted=True,
                    hard_delete=False,
                    trash_path=str(trash_path),
                )

        except FMFileNotFoundError as e:
            raise NotFoundError(
                f"File not found: {e.path}",
                resource_type="file",
                resource_id=str(e.path),
            ) from e
        except FileManagerError as e:
            raise ServiceError(f"Delete operation failed: {e}") from e

    async def restore_files(
        self,
        video_id: int,
        restore_path: Optional[str] = None,
    ) -> RestoreResult:
        """
        Restore a video's files from trash.

        Args:
            video_id: Video ID
            restore_path: Optional custom restore path

        Returns:
            RestoreResult with restored path

        Raises:
            NotFoundError: If video not found or not in trash
            ValidationError: If video is not deleted or has no file path
            ConflictError: If restore target already exists
            ServiceError: If restore operation fails
        """
        video = await self.get_by_id(video_id, include_deleted=True)
        file_manager = await self._get_file_manager()

        if not video.get("is_deleted"):
            raise ValidationError("Video is not deleted", field="is_deleted")

        current_path = video.get("video_file_path")
        current_nfo_path = video.get("nfo_file_path")

        if not current_path:
            raise ValidationError("Video has no file path", field="video_file_path")

        # Determine restore paths
        if restore_path:
            target_restore_path = Path(restore_path)
            target_nfo_path = target_restore_path.with_suffix(".nfo")
        else:
            # Calculate original location before trash
            # Use file_manager's paths (not global config) for test compatibility
            trash_dir = file_manager.trash_dir
            workspace_root = file_manager.workspace_root
            try:
                relative = Path(current_path).relative_to(trash_dir)
                target_restore_path = workspace_root / relative
                target_nfo_path = target_restore_path.with_suffix(".nfo")
            except ValueError:
                # Path isn't in trash - use as-is
                target_restore_path = Path(current_path)
                target_nfo_path = Path(current_nfo_path) if current_nfo_path else None

        try:
            restored_path = await file_manager.restore(
                video_id=video_id,
                trash_video_path=Path(current_path),
                restore_path=target_restore_path,
                repository=self.repository,
                trash_nfo_path=Path(current_nfo_path) if current_nfo_path else None,
                restore_nfo_path=target_nfo_path,
            )

            self.logger.info(
                "video_files_restored",
                video_id=video_id,
                restored_path=str(restored_path),
            )

            return RestoreResult(
                video_id=video_id,
                restored=True,
                restored_path=str(restored_path),
            )

        except FMFileNotFoundError as e:
            raise NotFoundError(
                f"File not found in trash: {e.path}",
                resource_type="trash_file",
                resource_id=str(e.path),
            ) from e
        except FMFileExistsError as e:
            raise ConflictError(
                f"Restore target already exists: {e.path}",
                conflicting_id=video_id,
                path=str(e.path),
            ) from e
        except FileManagerError as e:
            raise ServiceError(f"Restore operation failed: {e}") from e

    # ==================== Trash Management ====================

    async def list_trash(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List all videos in trash (soft-deleted).

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of deleted video records with metadata
        """
        videos = await self.repository.get_deleted_videos(limit=limit, offset=offset)

        # Enrich with file size info if available
        for video in videos:
            video_path = video.get("video_file_path")
            if video_path:
                try:
                    path = Path(video_path)
                    if path.exists():
                        video["file_size"] = path.stat().st_size
                    else:
                        video["file_size"] = None
                except Exception:
                    video["file_size"] = None
            else:
                video["file_size"] = None

        return videos

    async def get_trash_stats(self) -> Dict[str, Any]:
        """
        Get trash statistics.

        Returns:
            Dict with total_count, total_size_bytes
        """
        count = await self.repository.count_deleted_videos()
        videos = await self.repository.get_deleted_videos()

        total_size = 0
        for video in videos:
            video_path = video.get("video_file_path")
            if video_path:
                try:
                    path = Path(video_path)
                    if path.exists():
                        total_size += path.stat().st_size
                except Exception:
                    pass

        return {
            "total_count": count,
            "total_size_bytes": total_size,
        }

    async def empty_trash(self) -> Dict[str, Any]:
        """
        Permanently delete all trashed videos and their files.

        Returns:
            Dict with deleted_count and errors list
        """
        videos = await self.repository.get_deleted_videos()
        file_manager = await self._get_file_manager()

        deleted_count = 0
        errors: List[str] = []

        for video in videos:
            video_id = video["id"]
            video_path = video.get("video_file_path")
            nfo_path = video.get("nfo_file_path")

            try:
                if video_path:
                    await file_manager.hard_delete(
                        video_id=video_id,
                        video_path=Path(video_path),
                        repository=self.repository,
                        nfo_path=Path(nfo_path) if nfo_path else None,
                    )
                else:
                    # No file, just delete DB record
                    await self.repository.hard_delete_video(video_id)

                deleted_count += 1
            except Exception as e:
                error_msg = f"Video {video_id}: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(
                    "empty_trash_video_error",
                    video_id=video_id,
                    error=str(e),
                )

        self.logger.info(
            "trash_emptied",
            deleted_count=deleted_count,
            errors_count=len(errors),
        )

        return {
            "deleted_count": deleted_count,
            "errors": errors,
        }

    async def cleanup_old_trash(self, retention_days: int) -> Dict[str, Any]:
        """
        Delete items from trash older than retention period.

        Args:
            retention_days: Delete items older than this many days

        Returns:
            Dict with deleted_count and errors list
        """
        from datetime import datetime, timedelta, timezone

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        videos = await self.repository.get_deleted_videos()
        file_manager = await self._get_file_manager()

        deleted_count = 0
        errors: List[str] = []

        for video in videos:
            deleted_at = video.get("deleted_at")
            if not deleted_at:
                continue

            # Parse deleted_at timestamp
            try:
                if isinstance(deleted_at, str):
                    # ISO format timestamp
                    deleted_dt = datetime.fromisoformat(deleted_at.replace("Z", "+00:00"))
                else:
                    continue
            except (ValueError, TypeError):
                continue

            # Skip if not old enough
            if deleted_dt > cutoff_date:
                continue

            video_id = video["id"]
            video_path = video.get("video_file_path")
            nfo_path = video.get("nfo_file_path")

            try:
                if video_path:
                    await file_manager.hard_delete(
                        video_id=video_id,
                        video_path=Path(video_path),
                        repository=self.repository,
                        nfo_path=Path(nfo_path) if nfo_path else None,
                    )
                else:
                    await self.repository.hard_delete_video(video_id)

                deleted_count += 1
            except Exception as e:
                error_msg = f"Video {video_id}: {str(e)}"
                errors.append(error_msg)
                self.logger.warning(
                    "cleanup_old_trash_error",
                    video_id=video_id,
                    error=str(e),
                )

        self.logger.info(
            "old_trash_cleaned",
            retention_days=retention_days,
            deleted_count=deleted_count,
            errors_count=len(errors),
        )

        return {
            "deleted_count": deleted_count,
            "errors": errors,
        }

    # ==================== Duplicate Detection ====================

    async def find_duplicates(
        self,
        video_id: int,
        method: str = "all",
    ) -> DuplicatesResult:
        """
        Find potential duplicate videos.

        Args:
            video_id: Video ID to find duplicates for
            method: Detection method: 'hash', 'metadata', or 'all'

        Returns:
            DuplicatesResult with list of candidates

        Raises:
            NotFoundError: If video not found
        """
        await self.get_by_id(video_id)  # Verify exists
        file_manager = await self._get_file_manager()

        if method == "hash":
            duplicates = await file_manager.find_duplicates_by_hash(
                video_id=video_id,
                repository=self.repository,
            )
        elif method == "metadata":
            duplicates = await file_manager.find_duplicates_by_metadata(
                video_id=video_id,
                repository=self.repository,
            )
        else:
            duplicates = await file_manager.find_all_duplicates(
                video_id=video_id,
                repository=self.repository,
            )

        return DuplicatesResult(
            video_id=video_id,
            duplicates=duplicates,
            total=len(duplicates),
        )

    async def resolve_duplicates(
        self,
        keep_video_id: int,
        remove_video_ids: List[int],
        hard_delete: bool = False,
    ) -> ResolveResult:
        """
        Resolve duplicates by keeping one and removing others.

        Args:
            keep_video_id: ID of video to keep
            remove_video_ids: IDs of duplicate videos to remove
            hard_delete: If True, permanently delete. If False, soft delete.

        Returns:
            ResolveResult with removal statistics

        Raises:
            NotFoundError: If any video not found
            ServiceError: If resolution fails
        """
        # Verify keep video exists
        await self.get_by_id(keep_video_id)

        file_manager = await self._get_file_manager()
        removed_ids = []

        for remove_id in remove_video_ids:
            try:
                video = await self.get_by_id(remove_id, include_deleted=True)
                video_path = video.get("video_file_path")

                if video_path:
                    if hard_delete:
                        await file_manager.hard_delete(
                            video_id=remove_id,
                            video_path=Path(video_path),
                            repository=self.repository,
                        )
                    else:
                        await file_manager.soft_delete(
                            video_id=remove_id,
                            video_path=Path(video_path),
                            repository=self.repository,
                        )
                else:
                    # No file, just delete record
                    if hard_delete:
                        await self.repository.hard_delete_video(remove_id)
                    else:
                        await self.repository.delete_video(remove_id)

                removed_ids.append(remove_id)

            except Exception as e:
                self.logger.warning(
                    "duplicate_removal_failed",
                    video_id=remove_id,
                    error=str(e),
                )
                await self._report_failure(e, {"video_id": remove_id})

        self.logger.info(
            "duplicates_resolved",
            kept_id=keep_video_id,
            removed_count=len(removed_ids),
        )

        return ResolveResult(
            kept_video_id=keep_video_id,
            removed_count=len(removed_ids),
            removed_video_ids=removed_ids,
        )

    # ==================== Thumbnail Operations ====================

    async def get_thumbnail(
        self,
        video_id: int,
        timestamp: Optional[float] = None,
        regenerate: bool = False,
    ) -> Path:
        """
        Get or generate thumbnail for a video.

        Args:
            video_id: Video ID
            timestamp: Timestamp in seconds to extract frame (default: config value)
            regenerate: Force regeneration even if cached

        Returns:
            Path to the thumbnail image (JPEG)

        Raises:
            NotFoundError: If video not found or video file not found
            ValidationError: If video has no file path
        """
        video = await self.get_by_id(video_id)
        video_path = video.get("video_file_path")

        if not video_path:
            raise NotFoundError(
                "No video file associated with this video",
                resource_type="video_file",
                resource_id=str(video_id),
            )

        if not Path(video_path).exists():
            raise NotFoundError(
                "Video file not found on disk",
                resource_type="file",
                resource_id=video_path,
            )

        file_manager = await self._get_file_manager()

        return await file_manager.generate_thumbnail(
            video_id=video_id,
            video_path=Path(video_path),
            timestamp=timestamp,
            force=regenerate,
        )

    async def generate_prioritized_thumbnail(
        self,
        video_id: int,
        imvdb_id: Optional[int] = None,
        ytdlp_thumbnail_url: Optional[str] = None,
        video_path: Optional[Path] = None,
        duration: Optional[float] = None,
        force_ffmpeg: bool = False,
    ) -> Path:
        """
        Generate thumbnail using prioritized sources.

        Attempts to get thumbnail from external sources first, falling back
        to ffmpeg extraction from the video file.

        Priority order:
        1. IMVDb original image (if imvdb_id provided, fetches image URL)
        2. yt-dlp thumbnail URL (if provided)
        3. ffmpeg extraction at 20% of video duration

        Args:
            video_id: Video ID for caching
            imvdb_id: Optional IMVDb video ID to fetch image URL from
            ytdlp_thumbnail_url: Optional yt-dlp thumbnail URL
            video_path: Path to video file for ffmpeg fallback
            duration: Video duration in seconds (for 20% timestamp calculation)
            force_ffmpeg: If True, skip external sources and use ffmpeg only

        Returns:
            Path to the generated/cached thumbnail

        Raises:
            ServiceError: If thumbnail generation fails from all sources
        """
        import fuzzbin

        file_manager = await self._get_file_manager()

        # If forcing ffmpeg, skip external sources
        if force_ffmpeg:
            if not video_path:
                raise ValidationError(
                    "video_path required when force_ffmpeg=True",
                    field="video_path",
                )
            self.logger.info(
                "thumbnail_priority_ffmpeg_forced",
                video_id=video_id,
            )
            return await file_manager.generate_thumbnail(
                video_id=video_id,
                video_path=video_path,
                duration=duration,
                force=True,
            )

        # Try IMVDb original image first
        if imvdb_id:
            try:
                config = fuzzbin.get_config()
                imvdb_config = config.apis.get("imvdb") if config.apis else None

                if imvdb_config:
                    from fuzzbin.api.imvdb_client import IMVDbClient

                    async with IMVDbClient.from_config(imvdb_config) as client:
                        video_data = await client.get_video(imvdb_id)
                        # Extract thumbnail URL (prefer original, fall back to large)
                        if video_data.image:
                            imvdb_url = video_data.image.get("o") or video_data.image.get("l")
                            if imvdb_url:
                                self.logger.info(
                                    "thumbnail_priority_trying_imvdb",
                                    video_id=video_id,
                                    imvdb_id=imvdb_id,
                                    url=imvdb_url,
                                )
                                return await file_manager.download_external_thumbnail(
                                    video_id=video_id,
                                    url=imvdb_url,
                                    force=True,
                                )
            except Exception as e:
                self.logger.warning(
                    "thumbnail_priority_imvdb_failed",
                    video_id=video_id,
                    imvdb_id=imvdb_id,
                    error=str(e),
                )

        # Try yt-dlp thumbnail URL
        if ytdlp_thumbnail_url:
            try:
                self.logger.info(
                    "thumbnail_priority_trying_ytdlp",
                    video_id=video_id,
                    url=ytdlp_thumbnail_url,
                )
                return await file_manager.download_external_thumbnail(
                    video_id=video_id,
                    url=ytdlp_thumbnail_url,
                    force=True,
                )
            except Exception as e:
                self.logger.warning(
                    "thumbnail_priority_ytdlp_failed",
                    video_id=video_id,
                    url=ytdlp_thumbnail_url,
                    error=str(e),
                )

        # Fall back to ffmpeg extraction
        if video_path and video_path.exists():
            try:
                self.logger.info(
                    "thumbnail_priority_using_ffmpeg",
                    video_id=video_id,
                    video_path=str(video_path),
                    duration=duration,
                )
                return await file_manager.generate_thumbnail(
                    video_id=video_id,
                    video_path=video_path,
                    duration=duration,
                    force=True,
                )
            except Exception as e:
                self.logger.error(
                    "thumbnail_priority_ffmpeg_failed",
                    video_id=video_id,
                    error=str(e),
                )
                raise ServiceError(f"Failed to generate thumbnail: {e}") from e

        raise ServiceError("No thumbnail source available: no IMVDb ID, yt-dlp URL, or video file")

    async def refresh_video_properties(
        self,
        video_id: int,
        regenerate_thumbnail: bool = True,
    ) -> Dict[str, Any]:
        """
        Refresh video file properties using ffprobe and regenerate thumbnail.

        Runs ffprobe to re-analyze the video file and updates database with
        technical metadata (duration, resolution, codecs). Optionally regenerates
        the thumbnail using ffmpeg extraction.

        Args:
            video_id: Video ID to refresh
            regenerate_thumbnail: If True, regenerate thumbnail via ffmpeg

        Returns:
            Dict with refreshed properties:
            - media_info: Extracted metadata from ffprobe
            - thumbnail_path: Path to regenerated thumbnail (if requested)
            - thumbnail_timestamp: Unix timestamp for cache-busting

        Raises:
            NotFoundError: If video not found or no video file
            ServiceError: If ffprobe analysis fails
        """
        import time

        video = await self.get_by_id(video_id)
        video_path_str = video.get("video_file_path")

        if not video_path_str:
            raise NotFoundError(
                "No video file associated with this video",
                resource_type="video_file",
                resource_id=str(video_id),
            )

        video_path = Path(video_path_str)
        if not video_path.exists():
            raise NotFoundError(
                "Video file not found on disk",
                resource_type="file",
                resource_id=video_path_str,
            )

        file_manager = await self._get_file_manager()
        result: Dict[str, Any] = {
            "media_info": {},
            "thumbnail_path": None,
            "thumbnail_timestamp": None,
        }

        # Run ffprobe to extract media info
        try:
            media_info = await file_manager.validate_video_format(video_path)
            result["media_info"] = media_info

            # Update database with media info
            await self.repository.update_video(
                video_id,
                duration=media_info.get("duration"),
                width=media_info.get("width"),
                height=media_info.get("height"),
                video_codec=media_info.get("video_codec"),
                audio_codec=media_info.get("audio_codec"),
                container_format=media_info.get("container_format"),
                bitrate=media_info.get("bitrate"),
                frame_rate=media_info.get("frame_rate"),
                audio_channels=media_info.get("audio_channels"),
                audio_sample_rate=media_info.get("audio_sample_rate"),
            )

            self.logger.info(
                "video_properties_refreshed",
                video_id=video_id,
                duration=media_info.get("duration"),
                resolution=f"{media_info.get('width')}x{media_info.get('height')}",
            )
        except Exception as e:
            self.logger.error(
                "video_properties_refresh_ffprobe_failed",
                video_id=video_id,
                error=str(e),
            )
            raise ServiceError(f"Failed to analyze video: {e}") from e

        # Regenerate thumbnail if requested
        if regenerate_thumbnail:
            try:
                duration = media_info.get("duration")
                thumb_path = await file_manager.generate_thumbnail(
                    video_id=video_id,
                    video_path=video_path,
                    duration=duration,
                    force=True,
                )
                result["thumbnail_path"] = str(thumb_path)
                result["thumbnail_timestamp"] = int(time.time())

                self.logger.info(
                    "video_thumbnail_regenerated",
                    video_id=video_id,
                    thumbnail_path=str(thumb_path),
                )
            except Exception as e:
                self.logger.warning(
                    "video_thumbnail_regeneration_failed",
                    video_id=video_id,
                    error=str(e),
                )
                # Don't fail the whole operation if thumbnail fails

        return result

    # ==================== Library Operations ====================

    async def verify_library(self) -> LibraryReport:
        """
        Verify library integrity.

        Checks for:
        - Missing video files
        - Orphaned files (no DB record)
        - Broken NFO files
        - Path mismatches

        Returns:
            LibraryReport with issues found
        """
        file_manager = await self._get_file_manager()
        report = await file_manager.verify_library(self.repository)

        self.logger.info(
            "library_verified",
            videos_checked=report.videos_checked,
            total_issues=len(report.issues),
        )

        return report

    async def repair_library(
        self,
        repair_missing: bool = True,
        repair_broken_nfos: bool = True,
    ) -> Dict[str, int]:
        """
        Repair library issues.

        Args:
            repair_missing: Update status to 'missing' for videos with missing files
            repair_broken_nfos: Clear NFO path for videos with missing NFO files

        Returns:
            Dict with repair counts
        """
        report = await self.verify_library()

        repaired_missing = 0
        repaired_nfos = 0

        for issue in report.issues:
            try:
                if issue.issue_type == "missing_file" and repair_missing:
                    if issue.video_id:
                        await self.repository.update_status(
                            video_id=issue.video_id,
                            new_status="missing",
                            reason="File not found during library verification",
                            changed_by="library_repair",
                        )
                        repaired_missing += 1

                elif issue.issue_type == "broken_nfo" and repair_broken_nfos:
                    if issue.video_id:
                        await self.repository.update_video(
                            issue.video_id,
                            nfo_file_path=None,
                        )
                        repaired_nfos += 1

            except Exception as e:
                self.logger.warning(
                    "repair_failed",
                    issue_type=issue.issue_type,
                    video_id=issue.video_id,
                    error=str(e),
                )

        result = {
            "repaired_missing_files": repaired_missing,
            "repaired_broken_nfos": repaired_nfos,
            "total_repaired": repaired_missing + repaired_nfos,
        }

        self.logger.info("library_repaired", **result)
        return result

    # ==================== Cached Aggregations ====================

    @cached_async(ttl_seconds=60.0, maxsize=32)
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get library statistics (cached for 60 seconds).

        Returns:
            Dict with video counts by status, totals, etc.
        """
        # Get total count
        query = self.repository.query()
        total = await query.count()

        # Get counts by status
        status_counts = {}
        for status_value in ["discovered", "downloading", "downloaded", "organized", "missing"]:
            q = self.repository.query().where_status(status_value)
            status_counts[status_value] = await q.count()

        return {
            "total_videos": total,
            "by_status": status_counts,
        }
