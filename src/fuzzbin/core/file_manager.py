"""File manager for atomic file operations on media files.

This module provides high-level file operations with proper error handling,
rollback capabilities, and database synchronization. All file I/O uses aiofiles
for non-blocking operations.
"""

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import aiofiles
import aiofiles.os
import structlog

from ..common.config import FileManagerConfig, OrganizerConfig
from ..parsers.models import MusicVideoNFO
from .exceptions import InvalidPathError
from .organizer import build_media_paths, MediaPaths

if TYPE_CHECKING:
    from .db.repository import VideoRepository

logger = structlog.get_logger(__name__)


class FileManagerError(Exception):
    """Base exception for file manager errors."""

    pass


class FileNotFoundError(FileManagerError):
    """Raised when expected file is not found."""

    def __init__(self, message: str, path: Optional[Path] = None):
        super().__init__(message)
        self.path = path


class FileExistsError(FileManagerError):
    """Raised when target file already exists."""

    def __init__(self, message: str, path: Optional[Path] = None):
        super().__init__(message)
        self.path = path


class HashMismatchError(FileManagerError):
    """Raised when file hash verification fails after move."""

    def __init__(
        self,
        message: str,
        expected_hash: Optional[str] = None,
        actual_hash: Optional[str] = None,
    ):
        super().__init__(message)
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash


class FileTooLargeError(FileManagerError):
    """Raised when file exceeds maximum allowed size."""

    def __init__(
        self,
        message: str,
        file_size: Optional[int] = None,
        max_size: Optional[int] = None,
    ):
        super().__init__(message)
        self.file_size = file_size
        self.max_size = max_size


class RollbackError(FileManagerError):
    """Raised when file rollback fails."""

    def __init__(
        self,
        message: str,
        original_error: Optional[Exception] = None,
        rollback_error: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.original_error = original_error
        self.rollback_error = rollback_error


class DuplicateCandidate:
    """Represents a potential duplicate video."""

    def __init__(
        self,
        video_id: int,
        video_data: Dict[str, Any],
        match_type: str,
        confidence: float,
    ):
        """
        Initialize duplicate candidate.

        Args:
            video_id: ID of the potential duplicate video
            video_data: Full video record from database
            match_type: Type of match: 'hash', 'metadata', or 'both'
            confidence: Confidence score (0.0 to 1.0)
        """
        self.video_id = video_id
        self.video_data = video_data
        self.match_type = match_type
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "video_id": self.video_id,
            "match_type": self.match_type,
            "confidence": self.confidence,
            "title": self.video_data.get("title"),
            "artist": self.video_data.get("artist"),
            "file_path": self.video_data.get("video_file_path"),
            "file_hash": self.video_data.get("file_hash"),
        }


class LibraryIssue:
    """Represents an issue found during library verification."""

    def __init__(
        self,
        issue_type: str,
        video_id: Optional[int],
        path: Optional[str],
        message: str,
        repair_action: Optional[str] = None,
    ):
        """
        Initialize library issue.

        Args:
            issue_type: Type of issue: 'missing_file', 'orphaned_file', 'broken_nfo', 'path_mismatch'
            video_id: Video ID (if applicable)
            path: File path involved
            message: Human-readable description
            repair_action: Suggested repair action
        """
        self.issue_type = issue_type
        self.video_id = video_id
        self.path = path
        self.message = message
        self.repair_action = repair_action

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "issue_type": self.issue_type,
            "video_id": self.video_id,
            "path": self.path,
            "message": self.message,
            "repair_action": self.repair_action,
        }


class LibraryReport:
    """Report from library verification."""

    def __init__(self):
        """Initialize empty report."""
        self.issues: List[LibraryIssue] = []
        self.videos_checked: int = 0
        self.files_scanned: int = 0
        self.missing_files: int = 0
        self.orphaned_files: int = 0
        self.broken_nfos: int = 0
        self.path_mismatches: int = 0

    def add_issue(self, issue: LibraryIssue) -> None:
        """Add an issue to the report."""
        self.issues.append(issue)
        if issue.issue_type == "missing_file":
            self.missing_files += 1
        elif issue.issue_type == "orphaned_file":
            self.orphaned_files += 1
        elif issue.issue_type == "broken_nfo":
            self.broken_nfos += 1
        elif issue.issue_type == "path_mismatch":
            self.path_mismatches += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "videos_checked": self.videos_checked,
            "files_scanned": self.files_scanned,
            "missing_files": self.missing_files,
            "orphaned_files": self.orphaned_files,
            "broken_nfos": self.broken_nfos,
            "path_mismatches": self.path_mismatches,
            "total_issues": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
        }


class FileManager:
    """Manages file operations for media library.
    
    This class provides atomic file operations with rollback support,
    duplicate detection, and library verification capabilities.
    All file I/O uses aiofiles for non-blocking operations.
    
    Example:
        >>> from fuzzbin.common.config import FileManagerConfig
        >>> config = FileManagerConfig(trash_dir=".trash", hash_algorithm="sha256")
        >>> fm = FileManager(config, workspace_root=Path("/media"))
        >>> 
        >>> # Move video to organized location
        >>> paths = await fm.move_video_atomic(
        ...     video_id=123,
        ...     source_path=Path("/downloads/video.mp4"),
        ...     target_paths=MediaPaths(...),
        ...     repository=repo,
        ... )
    """

    def __init__(
        self,
        config: FileManagerConfig,
        workspace_root: Path,
        organizer_config: Optional[OrganizerConfig] = None,
    ):
        """
        Initialize file manager.

        Args:
            config: FileManagerConfig with trash_dir, hash_algorithm, etc.
            workspace_root: Root directory for media files
            organizer_config: Optional OrganizerConfig for path generation
        """
        self.config = config
        self.workspace_root = Path(workspace_root)
        self.organizer_config = organizer_config
        self.trash_dir = self.workspace_root / config.trash_dir

        logger.info(
            "file_manager_initialized",
            workspace_root=str(self.workspace_root),
            trash_dir=str(self.trash_dir),
            hash_algorithm=config.hash_algorithm,
        )

    @classmethod
    def from_config(
        cls,
        file_manager_config: FileManagerConfig,
        workspace_root: Path,
        organizer_config: Optional[OrganizerConfig] = None,
    ) -> "FileManager":
        """
        Create FileManager from configuration.

        Args:
            file_manager_config: File manager configuration
            workspace_root: Root directory for media files
            organizer_config: Optional organizer configuration

        Returns:
            Configured FileManager instance
        """
        return cls(
            config=file_manager_config,
            workspace_root=workspace_root,
            organizer_config=organizer_config,
        )

    async def compute_file_hash(self, file_path: Path) -> str:
        """
        Compute hash of a file using configured algorithm.

        Args:
            file_path: Path to file to hash

        Returns:
            Hex digest of file hash

        Raises:
            FileNotFoundError: If file doesn't exist
            FileTooLargeError: If file exceeds max_file_size
        """
        if not file_path.exists():
            raise FileNotFoundError(
                f"File not found: {file_path}",
                path=file_path,
            )

        # Check file size limit
        file_size = file_path.stat().st_size
        if self.config.max_file_size and file_size > self.config.max_file_size:
            raise FileTooLargeError(
                f"File size {file_size} exceeds maximum {self.config.max_file_size}",
                file_size=file_size,
                max_size=self.config.max_file_size,
            )

        # Select hash algorithm
        algorithm = self.config.hash_algorithm.lower()
        if algorithm == "xxhash":
            try:
                import xxhash
                hasher = xxhash.xxh64()
            except ImportError:
                logger.warning(
                    "xxhash_not_available",
                    fallback="sha256",
                )
                hasher = hashlib.sha256()
        elif algorithm == "md5":
            hasher = hashlib.md5()
        else:
            hasher = hashlib.sha256()

        # Read file in chunks
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                chunk = await f.read(self.config.chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)

        file_hash = hasher.hexdigest()

        logger.debug(
            "file_hash_computed",
            file_path=str(file_path),
            algorithm=algorithm,
            hash=file_hash[:16] + "...",
        )

        return file_hash

    async def verify_file_exists(self, file_path: Path) -> bool:
        """
        Check if file exists asynchronously.

        Args:
            file_path: Path to check

        Returns:
            True if file exists
        """
        try:
            return await aiofiles.os.path.exists(file_path)
        except Exception as e:
            logger.error(
                "file_exists_check_failed",
                file_path=str(file_path),
                error=str(e),
            )
            return False

    async def _ensure_directory(self, dir_path: Path) -> None:
        """Ensure directory exists, creating if necessary."""
        if not await aiofiles.os.path.exists(dir_path):
            await aiofiles.os.makedirs(dir_path)
            logger.debug("directory_created", path=str(dir_path))

    async def _copy_file(self, source: Path, target: Path) -> None:
        """Copy file asynchronously."""
        await self._ensure_directory(target.parent)
        
        async with aiofiles.open(source, "rb") as src:
            async with aiofiles.open(target, "wb") as dst:
                while True:
                    chunk = await src.read(self.config.chunk_size)
                    if not chunk:
                        break
                    await dst.write(chunk)

    async def _move_file(self, source: Path, target: Path) -> None:
        """
        Move file atomically when possible.
        
        Uses rename for same-filesystem moves, copy+delete for cross-filesystem.
        """
        await self._ensure_directory(target.parent)
        
        try:
            # Try atomic rename first (same filesystem)
            await aiofiles.os.rename(source, target)
        except OSError:
            # Cross-filesystem: copy then delete
            await self._copy_file(source, target)
            await aiofiles.os.remove(source)

    async def move_video_atomic(
        self,
        video_id: int,
        source_video_path: Path,
        target_paths: MediaPaths,
        repository: "VideoRepository",
        source_nfo_path: Optional[Path] = None,
        dry_run: bool = False,
    ) -> MediaPaths:
        """
        Move video (and optionally NFO) files atomically with DB sync.

        This operation:
        1. Computes hash of source file (if verify_after_move enabled)
        2. Moves video file to temp location
        3. Moves NFO file to temp location (if provided)
        4. Renames temp files to final locations
        5. Updates database with new paths
        6. Verifies hash of moved file (if enabled)

        On any failure, rolls back file moves before raising exception.

        Args:
            video_id: ID of video in database
            source_video_path: Current location of video file
            target_paths: Target MediaPaths from build_media_paths
            repository: VideoRepository for database updates
            source_nfo_path: Optional current location of NFO file
            dry_run: If True, only validate without making changes

        Returns:
            MediaPaths with final file locations

        Raises:
            FileNotFoundError: If source file doesn't exist
            FileExistsError: If target file already exists
            HashMismatchError: If post-move hash verification fails
            RollbackError: If rollback after failure also fails
        """
        # Validate source exists
        if not await self.verify_file_exists(source_video_path):
            raise FileNotFoundError(
                f"Source video not found: {source_video_path}",
                path=source_video_path,
            )

        # Check target doesn't exist
        if await self.verify_file_exists(target_paths.video_path):
            raise FileExistsError(
                f"Target video already exists: {target_paths.video_path}",
                path=target_paths.video_path,
            )

        if dry_run:
            logger.info(
                "move_video_dry_run",
                video_id=video_id,
                source=str(source_video_path),
                target_video=str(target_paths.video_path),
                target_nfo=str(target_paths.nfo_path),
            )
            return target_paths

        # Compute source hash before move (if verification enabled)
        source_hash: Optional[str] = None
        if self.config.verify_after_move:
            source_hash = await self.compute_file_hash(source_video_path)

        # Track files for rollback
        moved_files: List[Tuple[Path, Path]] = []

        try:
            # Move video file
            await self._move_file(source_video_path, target_paths.video_path)
            moved_files.append((target_paths.video_path, source_video_path))

            # Move NFO file if provided
            if source_nfo_path and await self.verify_file_exists(source_nfo_path):
                await self._move_file(source_nfo_path, target_paths.nfo_path)
                moved_files.append((target_paths.nfo_path, source_nfo_path))

            # Verify hash after move
            if self.config.verify_after_move and source_hash:
                target_hash = await self.compute_file_hash(target_paths.video_path)
                if target_hash != source_hash:
                    raise HashMismatchError(
                        f"Hash mismatch after move: expected {source_hash}, got {target_hash}",
                        expected_hash=source_hash,
                        actual_hash=target_hash,
                    )

            # Update database with new paths
            await repository.update_video(
                video_id,
                video_file_path=str(target_paths.video_path),
                nfo_file_path=str(target_paths.nfo_path) if source_nfo_path else None,
                file_hash=source_hash,
                status="organized",
            )

            logger.info(
                "video_moved_successfully",
                video_id=video_id,
                source_video=str(source_video_path),
                target_video=str(target_paths.video_path),
                hash_verified=self.config.verify_after_move,
            )

            return target_paths

        except Exception as e:
            # Rollback file moves
            logger.warning(
                "move_failed_rolling_back",
                video_id=video_id,
                error=str(e),
                files_to_rollback=len(moved_files),
            )

            rollback_errors = []
            for current_path, original_path in reversed(moved_files):
                try:
                    if await self.verify_file_exists(current_path):
                        await self._move_file(current_path, original_path)
                        logger.debug(
                            "file_rolled_back",
                            from_path=str(current_path),
                            to_path=str(original_path),
                        )
                except Exception as rollback_e:
                    rollback_errors.append((current_path, rollback_e))

            if rollback_errors:
                raise RollbackError(
                    f"Rollback failed for {len(rollback_errors)} files after: {e}",
                    original_error=e,
                    rollback_error=rollback_errors[0][1],
                )

            # Re-raise original error if rollback succeeded
            raise

    async def soft_delete(
        self,
        video_id: int,
        video_path: Path,
        repository: "VideoRepository",
        nfo_path: Optional[Path] = None,
    ) -> Path:
        """
        Move files to trash directory (soft delete).

        Files are moved to trash_dir with structure preserving relative paths.
        Database record is marked as deleted but preserved.

        Args:
            video_id: Video ID in database
            video_path: Current video file path
            repository: VideoRepository for database updates
            nfo_path: Optional NFO file path

        Returns:
            Path to video file in trash

        Raises:
            FileNotFoundError: If video file doesn't exist
        """
        if not await self.verify_file_exists(video_path):
            raise FileNotFoundError(
                f"Video file not found: {video_path}",
                path=video_path,
            )

        # Calculate trash path preserving directory structure
        try:
            relative_path = video_path.relative_to(self.workspace_root)
        except ValueError:
            # File is outside workspace, use filename only
            relative_path = video_path.name

        trash_video_path = self.trash_dir / relative_path
        trash_nfo_path = self.trash_dir / Path(str(relative_path)).with_suffix(".nfo")

        # Ensure trash directory exists
        await self._ensure_directory(self.trash_dir)

        # Move video to trash
        await self._move_file(video_path, trash_video_path)

        # Move NFO if exists
        if nfo_path and await self.verify_file_exists(nfo_path):
            await self._move_file(nfo_path, trash_nfo_path)

        # Update database - mark as deleted
        await repository.delete_video(video_id)
        await repository.update_video(
            video_id,
            video_file_path=str(trash_video_path),
            nfo_file_path=str(trash_nfo_path) if nfo_path else None,
        )

        logger.info(
            "video_soft_deleted",
            video_id=video_id,
            original_path=str(video_path),
            trash_path=str(trash_video_path),
        )

        return trash_video_path

    async def restore(
        self,
        video_id: int,
        trash_video_path: Path,
        restore_path: Path,
        repository: "VideoRepository",
        trash_nfo_path: Optional[Path] = None,
        restore_nfo_path: Optional[Path] = None,
    ) -> Path:
        """
        Restore files from trash directory.

        Args:
            video_id: Video ID in database
            trash_video_path: Video file path in trash
            restore_path: Target path to restore video to
            repository: VideoRepository for database updates
            trash_nfo_path: Optional NFO path in trash
            restore_nfo_path: Optional target NFO restore path

        Returns:
            Path to restored video file

        Raises:
            FileNotFoundError: If trash file doesn't exist
            FileExistsError: If restore target already exists
        """
        if not await self.verify_file_exists(trash_video_path):
            raise FileNotFoundError(
                f"Trash file not found: {trash_video_path}",
                path=trash_video_path,
            )

        if await self.verify_file_exists(restore_path):
            raise FileExistsError(
                f"Restore target already exists: {restore_path}",
                path=restore_path,
            )

        # Move video from trash
        await self._move_file(trash_video_path, restore_path)

        # Move NFO if provided
        if trash_nfo_path and restore_nfo_path:
            if await self.verify_file_exists(trash_nfo_path):
                await self._move_file(trash_nfo_path, restore_nfo_path)

        # Update database - restore
        now = datetime.now(timezone.utc).isoformat()
        await repository.update_video(
            video_id,
            is_deleted=0,
            deleted_at=None,
            video_file_path=str(restore_path),
            nfo_file_path=str(restore_nfo_path) if restore_nfo_path else None,
            updated_at=now,
        )

        logger.info(
            "video_restored",
            video_id=video_id,
            trash_path=str(trash_video_path),
            restored_path=str(restore_path),
        )

        return restore_path

    async def hard_delete(
        self,
        video_id: int,
        video_path: Path,
        repository: "VideoRepository",
        nfo_path: Optional[Path] = None,
    ) -> None:
        """
        Permanently delete files and database record.

        Args:
            video_id: Video ID in database
            video_path: Video file path
            repository: VideoRepository for database updates
            nfo_path: Optional NFO file path
        """
        # Delete video file if exists
        if await self.verify_file_exists(video_path):
            await aiofiles.os.remove(video_path)
            logger.debug("file_deleted", path=str(video_path))

        # Delete NFO if exists
        if nfo_path and await self.verify_file_exists(nfo_path):
            await aiofiles.os.remove(nfo_path)
            logger.debug("file_deleted", path=str(nfo_path))

        # Hard delete from database
        await repository.hard_delete_video(video_id)

        logger.info(
            "video_hard_deleted",
            video_id=video_id,
            video_path=str(video_path),
        )

    async def organize_video(
        self,
        video_id: int,
        repository: "VideoRepository",
        nfo_data: MusicVideoNFO,
        dry_run: bool = False,
    ) -> MediaPaths:
        """
        Organize a video file using path pattern from config.

        Fetches current video location from database, generates organized path
        using build_media_paths, and moves files atomically.

        Args:
            video_id: Video ID in database
            repository: VideoRepository instance
            nfo_data: MusicVideoNFO with metadata for path generation
            dry_run: If True, only return target paths without moving

        Returns:
            MediaPaths with final (or proposed) file locations

        Raises:
            ValueError: If organizer_config not provided
            FileNotFoundError: If current video file not found
        """
        if not self.organizer_config:
            raise ValueError(
                "OrganizerConfig required for organize_video. "
                "Provide organizer_config when initializing FileManager."
            )

        # Get current video from database
        video = await repository.get_video_by_id(video_id)
        current_path = Path(video["video_file_path"])
        current_nfo_path = (
            Path(video["nfo_file_path"]) if video.get("nfo_file_path") else None
        )

        # Generate target paths
        target_paths = build_media_paths(
            root_path=self.workspace_root,
            nfo_data=nfo_data,
            config=self.organizer_config,
        )

        # Check if already organized
        if current_path == target_paths.video_path:
            logger.info(
                "video_already_organized",
                video_id=video_id,
                path=str(current_path),
            )
            return target_paths

        # Move files
        return await self.move_video_atomic(
            video_id=video_id,
            source_video_path=current_path,
            target_paths=target_paths,
            repository=repository,
            source_nfo_path=current_nfo_path,
            dry_run=dry_run,
        )

    async def find_duplicates_by_hash(
        self,
        video_id: int,
        repository: "VideoRepository",
    ) -> List[DuplicateCandidate]:
        """
        Find duplicate videos by file hash.

        Args:
            video_id: Video ID to find duplicates for
            repository: VideoRepository instance

        Returns:
            List of DuplicateCandidate with matching hashes
        """
        video = await repository.get_video_by_id(video_id)
        file_hash = video.get("file_hash")

        if not file_hash:
            # Need to compute hash first
            video_path = video.get("video_file_path")
            if not video_path or not await self.verify_file_exists(Path(video_path)):
                return []
            file_hash = await self.compute_file_hash(Path(video_path))
            await repository.update_video(video_id, file_hash=file_hash)

        # Query for other videos with same hash
        # Using raw query since this isn't in the standard query builder
        duplicates: List[DuplicateCandidate] = []
        
        if repository._connection is None:
            return duplicates

        cursor = await repository._connection.execute(
            """
            SELECT * FROM videos 
            WHERE file_hash = ? AND id != ? AND is_deleted = 0
            """,
            (file_hash, video_id),
        )
        rows = await cursor.fetchall()

        for row in rows:
            row_dict = dict(row)
            duplicates.append(
                DuplicateCandidate(
                    video_id=row_dict["id"],
                    video_data=row_dict,
                    match_type="hash",
                    confidence=1.0,  # Exact hash match
                )
            )

        logger.info(
            "duplicates_found_by_hash",
            video_id=video_id,
            hash=file_hash[:16] + "...",
            duplicate_count=len(duplicates),
        )

        return duplicates

    async def find_duplicates_by_metadata(
        self,
        video_id: int,
        repository: "VideoRepository",
    ) -> List[DuplicateCandidate]:
        """
        Find duplicate videos by metadata (title, artist, duration).

        Args:
            video_id: Video ID to find duplicates for
            repository: VideoRepository instance

        Returns:
            List of DuplicateCandidate with matching metadata
        """
        video = await repository.get_video_by_id(video_id)
        title = video.get("title", "").lower().strip()
        artist = video.get("artist", "").lower().strip()

        if not title:
            return []

        duplicates: List[DuplicateCandidate] = []
        
        if repository._connection is None:
            return duplicates

        # Query for videos with matching title and artist
        cursor = await repository._connection.execute(
            """
            SELECT * FROM videos 
            WHERE LOWER(TRIM(title)) = ? 
            AND LOWER(TRIM(COALESCE(artist, ''))) = ?
            AND id != ? 
            AND is_deleted = 0
            """,
            (title, artist, video_id),
        )
        rows = await cursor.fetchall()

        for row in rows:
            row_dict = dict(row)
            # Calculate confidence based on matching fields
            confidence = 0.7  # Base confidence for title+artist match

            # Boost confidence for matching year
            if video.get("year") and row_dict.get("year") == video.get("year"):
                confidence += 0.1

            # Boost confidence for matching album
            if (
                video.get("album")
                and row_dict.get("album")
                and video.get("album").lower() == row_dict.get("album", "").lower()
            ):
                confidence += 0.1

            # Cap at 0.95 (not 1.0 since it's metadata, not hash match)
            confidence = min(confidence, 0.95)

            duplicates.append(
                DuplicateCandidate(
                    video_id=row_dict["id"],
                    video_data=row_dict,
                    match_type="metadata",
                    confidence=confidence,
                )
            )

        logger.info(
            "duplicates_found_by_metadata",
            video_id=video_id,
            title=title,
            artist=artist,
            duplicate_count=len(duplicates),
        )

        return duplicates

    async def find_all_duplicates(
        self,
        video_id: int,
        repository: "VideoRepository",
    ) -> List[DuplicateCandidate]:
        """
        Find all potential duplicates using both hash and metadata.

        Combines results from hash and metadata searches, deduplicating
        and updating match_type to 'both' when found by both methods.

        Args:
            video_id: Video ID to find duplicates for
            repository: VideoRepository instance

        Returns:
            List of DuplicateCandidate sorted by confidence (highest first)
        """
        # Get both sets of duplicates
        hash_dupes = await self.find_duplicates_by_hash(video_id, repository)
        metadata_dupes = await self.find_duplicates_by_metadata(video_id, repository)

        # Merge results
        results: Dict[int, DuplicateCandidate] = {}

        for dupe in hash_dupes:
            results[dupe.video_id] = dupe

        for dupe in metadata_dupes:
            if dupe.video_id in results:
                # Found by both methods - upgrade match type and confidence
                existing = results[dupe.video_id]
                existing.match_type = "both"
                existing.confidence = 1.0  # Maximum confidence
            else:
                results[dupe.video_id] = dupe

        # Sort by confidence descending
        sorted_dupes = sorted(
            results.values(),
            key=lambda d: d.confidence,
            reverse=True,
        )

        return sorted_dupes

    async def verify_library(
        self,
        repository: "VideoRepository",
        scan_orphans: bool = True,
    ) -> LibraryReport:
        """
        Verify library integrity by checking DB paths vs filesystem.

        Checks:
        1. Videos in DB have existing files
        2. NFO paths in DB are valid
        3. (Optional) Files in workspace not in DB (orphans)

        Args:
            repository: VideoRepository instance
            scan_orphans: Whether to scan for orphaned files

        Returns:
            LibraryReport with issues found
        """
        report = LibraryReport()

        # Get all non-deleted videos
        videos = await repository.query().execute()
        report.videos_checked = len(videos)

        # Check each video's files
        for video in videos:
            video_id = video["id"]
            video_path = video.get("video_file_path")
            nfo_path = video.get("nfo_file_path")

            # Check video file
            if video_path:
                if not await self.verify_file_exists(Path(video_path)):
                    report.add_issue(
                        LibraryIssue(
                            issue_type="missing_file",
                            video_id=video_id,
                            path=video_path,
                            message=f"Video file not found: {video_path}",
                            repair_action="update_status_to_missing",
                        )
                    )

            # Check NFO file
            if nfo_path:
                if not await self.verify_file_exists(Path(nfo_path)):
                    report.add_issue(
                        LibraryIssue(
                            issue_type="broken_nfo",
                            video_id=video_id,
                            path=nfo_path,
                            message=f"NFO file not found: {nfo_path}",
                            repair_action="clear_nfo_path",
                        )
                    )

        # Scan for orphaned files
        if scan_orphans:
            known_paths = {
                v.get("video_file_path")
                for v in videos
                if v.get("video_file_path")
            }
            known_paths.update({
                v.get("nfo_file_path")
                for v in videos
                if v.get("nfo_file_path")
            })

            # Walk workspace looking for video files
            video_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
            
            for root, _, files in os.walk(self.workspace_root):
                # Skip trash directory
                root_path = Path(root)
                if self.trash_dir in root_path.parents or root_path == self.trash_dir:
                    continue

                for filename in files:
                    file_path = root_path / filename
                    report.files_scanned += 1

                    # Check if it's a video file not in database
                    if file_path.suffix.lower() in video_extensions:
                        if str(file_path) not in known_paths:
                            report.add_issue(
                                LibraryIssue(
                                    issue_type="orphaned_file",
                                    video_id=None,
                                    path=str(file_path),
                                    message=f"Video file not in database: {file_path}",
                                    repair_action="import_or_delete",
                                )
                            )

        logger.info(
            "library_verified",
            videos_checked=report.videos_checked,
            files_scanned=report.files_scanned,
            issues_found=len(report.issues),
        )

        return report

    async def repair_missing_file(
        self,
        video_id: int,
        repository: "VideoRepository",
    ) -> None:
        """
        Repair a missing file issue by updating video status.

        Args:
            video_id: Video ID with missing file
            repository: VideoRepository instance
        """
        await repository.update_video(
            video_id,
            status="missing",
        )
        logger.info("repaired_missing_file", video_id=video_id)

    async def repair_broken_nfo(
        self,
        video_id: int,
        repository: "VideoRepository",
    ) -> None:
        """
        Repair a broken NFO link by clearing the path.

        Args:
            video_id: Video ID with broken NFO
            repository: VideoRepository instance
        """
        await repository.update_video(
            video_id,
            nfo_file_path=None,
            nfo_file_path_relative=None,
        )
        logger.info("repaired_broken_nfo", video_id=video_id)
