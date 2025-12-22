"""Backup service for creating comprehensive system backups.

This service creates portable .zip archives containing:
- config.yaml: User configuration file
- fuzzbin.db: Library database (via SQLite backup API)
- .thumbnails/: Thumbnail repository directory

Backups can be triggered on-demand via API or scheduled via cron jobs.
Archives are self-contained and can be restored manually without the program running.

Example:
    >>> from fuzzbin.services import BackupService
    >>> import fuzzbin
    >>>
    >>> config = fuzzbin.get_config()
    >>> backup_service = BackupService(config)
    >>> backup_info = await backup_service.create_backup()
    >>> print(f"Created backup: {backup_info['filename']}")
"""

import asyncio
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite
import structlog

from fuzzbin.core.db.backup import DatabaseBackup
from fuzzbin.core.db.exceptions import BackupError

logger = structlog.get_logger(__name__)


class BackupService:
    """Service for creating and managing system backups.

    Creates timestamped .zip archives containing config.yaml, the SQLite database,
    and the thumbnail repository. Supports automatic cleanup of old backups based
    on retention count.

    Attributes:
        config: Fuzzbin configuration object
        backup_dir: Directory where backup archives are stored
    """

    # Files/directories to include in backup
    BACKUP_ITEMS = {
        "config": "config.yaml",
        "database": "fuzzbin.db",
        "thumbnails": ".thumbnails",
    }

    def __init__(self, config: Any) -> None:
        """
        Initialize backup service.

        Args:
            config: Fuzzbin Config object with path information
        """
        self.config = config
        self.backup_dir = config.get_backup_dir()

    async def create_backup(self, description: str | None = None) -> dict[str, Any]:
        """
        Create a complete system backup.

        Creates a timestamped .zip archive containing:
        - config.yaml from config_dir
        - fuzzbin.db (using SQLite backup API after WAL checkpoint)
        - .thumbnails directory with all cached thumbnails

        Args:
            description: Optional description for the backup

        Returns:
            Dict with backup metadata:
                - filename: Name of the backup file
                - path: Full path to backup file
                - size_bytes: Size of backup in bytes
                - created_at: ISO timestamp of creation
                - contains: List of items included in backup
                - description: Optional description

        Raises:
            BackupError: If backup creation fails
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"fuzzbin_backup_{timestamp}.zip"
        backup_path = self.backup_dir / backup_filename

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        config_dir = self.config.config_dir
        db_path = self.config.get_database_path()
        thumbnail_dir = self.config.get_thumbnail_dir()

        logger.info(
            "backup_starting",
            backup_path=str(backup_path),
            config_dir=str(config_dir),
            db_path=str(db_path),
            thumbnail_dir=str(thumbnail_dir),
        )

        contains: list[str] = []

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # 1. Backup database with WAL checkpoint
                if db_path.exists():
                    await self._backup_database(db_path, temp_path / "fuzzbin.db")
                    contains.append("database")

                # 2. Copy config.yaml
                config_file = config_dir / "config.yaml"
                if config_file.exists():
                    shutil.copy2(config_file, temp_path / "config.yaml")
                    contains.append("config")

                # 3. Copy thumbnails directory
                if thumbnail_dir.exists() and any(thumbnail_dir.iterdir()):
                    shutil.copytree(
                        thumbnail_dir,
                        temp_path / ".thumbnails",
                        dirs_exist_ok=True,
                    )
                    contains.append("thumbnails")

                # 4. Create zip archive
                await self._create_zip_archive(temp_path, backup_path)

            # Get backup metadata
            stat = backup_path.stat()
            backup_info = {
                "filename": backup_filename,
                "path": str(backup_path),
                "size_bytes": stat.st_size,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "contains": contains,
                "description": description,
            }

            logger.info(
                "backup_created",
                filename=backup_filename,
                size_bytes=stat.st_size,
                contains=contains,
            )

            return backup_info

        except Exception as e:
            logger.error(
                "backup_failed",
                backup_path=str(backup_path),
                error=str(e),
            )
            # Clean up partial backup
            if backup_path.exists():
                backup_path.unlink()
            raise BackupError(
                f"Failed to create backup: {e}",
                backup_path=backup_path,
            ) from e

    async def _backup_database(self, source_db: Path, target_path: Path) -> None:
        """
        Backup database with WAL checkpoint for minimal size.

        Args:
            source_db: Path to source database
            target_path: Path for backup file
        """
        # First, checkpoint the WAL file to minimize backup size
        try:
            async with aiosqlite.connect(str(source_db)) as conn:
                await conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.debug("wal_checkpoint_completed", source_db=str(source_db))
        except Exception as e:
            # WAL checkpoint failure is not fatal - proceed with backup
            logger.warning(
                "wal_checkpoint_failed",
                source_db=str(source_db),
                error=str(e),
            )

        # Use SQLite backup API for atomic, consistent backup
        await DatabaseBackup.backup(source_db, target_path)

    async def _create_zip_archive(self, source_dir: Path, target_path: Path) -> None:
        """
        Create zip archive from directory contents.

        Args:
            source_dir: Directory containing files to archive
            target_path: Path for the zip file
        """
        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._sync_create_zip,
            source_dir,
            target_path,
        )

    def _sync_create_zip(self, source_dir: Path, target_path: Path) -> None:
        """Synchronous zip creation helper."""
        with zipfile.ZipFile(target_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zf.write(file_path, arcname)

    def list_backups(self) -> list[dict[str, Any]]:
        """
        List available backup files.

        Returns:
            List of backup metadata dicts sorted by creation time (newest first):
                - filename: Backup filename
                - path: Full path to backup
                - size_bytes: File size in bytes
                - created_at: ISO timestamp (from filename)
                - contains: List of items (from zip inspection)
        """
        if not self.backup_dir.exists():
            return []

        backups = []
        for backup_file in self.backup_dir.glob("fuzzbin_backup_*.zip"):
            try:
                stat = backup_file.stat()

                # Parse timestamp from filename
                # Format: fuzzbin_backup_YYYYMMDD_HHMMSS.zip
                name_parts = backup_file.stem.split("_")
                if len(name_parts) >= 4:
                    date_str = f"{name_parts[2]}_{name_parts[3]}"
                    try:
                        created_dt = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                        created_at = created_dt.replace(tzinfo=timezone.utc).isoformat()
                    except ValueError:
                        created_at = datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat()
                else:
                    created_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

                # Inspect zip contents
                contains = self._inspect_backup_contents(backup_file)

                backups.append(
                    {
                        "filename": backup_file.name,
                        "path": str(backup_file),
                        "size_bytes": stat.st_size,
                        "created_at": created_at,
                        "contains": contains,
                    }
                )

            except (OSError, zipfile.BadZipFile) as e:
                logger.warning(
                    "backup_inspection_failed",
                    backup_file=str(backup_file),
                    error=str(e),
                )
                continue

        # Sort by creation time, newest first
        backups.sort(key=lambda x: x["created_at"], reverse=True)

        return backups

    def _inspect_backup_contents(self, backup_path: Path) -> list[str]:
        """
        Inspect backup zip to determine what it contains.

        Args:
            backup_path: Path to backup zip file

        Returns:
            List of content identifiers: 'config', 'database', 'thumbnails'
        """
        contains = []
        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                names = zf.namelist()
                if "config.yaml" in names:
                    contains.append("config")
                if "fuzzbin.db" in names:
                    contains.append("database")
                if any(name.startswith(".thumbnails/") for name in names):
                    contains.append("thumbnails")
        except zipfile.BadZipFile:
            pass
        return contains

    def cleanup_old_backups(self, retention_count: int) -> list[str]:
        """
        Delete oldest backups exceeding retention count.

        Args:
            retention_count: Number of backups to keep

        Returns:
            List of deleted backup filenames
        """
        if retention_count < 1:
            logger.warning("cleanup_skipped", reason="retention_count_too_low")
            return []

        backups = self.list_backups()

        if len(backups) <= retention_count:
            logger.debug(
                "cleanup_not_needed",
                backup_count=len(backups),
                retention_count=retention_count,
            )
            return []

        # Delete oldest backups (list is sorted newest first)
        to_delete = backups[retention_count:]
        deleted = []

        for backup in to_delete:
            try:
                backup_path = Path(backup["path"])
                backup_path.unlink()
                deleted.append(backup["filename"])
                logger.info(
                    "backup_deleted",
                    filename=backup["filename"],
                    age_reason="exceeded_retention_count",
                )
            except OSError as e:
                logger.error(
                    "backup_delete_failed",
                    filename=backup["filename"],
                    error=str(e),
                )

        logger.info(
            "backup_cleanup_completed",
            deleted_count=len(deleted),
            remaining_count=len(backups) - len(deleted),
        )

        return deleted

    async def verify_backup(self, filename: str) -> dict[str, Any]:
        """
        Verify backup integrity and contents.

        Args:
            filename: Backup filename to verify

        Returns:
            Dict with verification results:
                - valid: True if backup is valid
                - filename: Backup filename
                - contains: List of items in backup
                - database_valid: True if database passes integrity check
                - errors: List of error messages (if any)

        Raises:
            FileNotFoundError: If backup file doesn't exist
        """
        backup_path = self.backup_dir / filename

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {filename}")

        result = {
            "valid": True,
            "filename": filename,
            "contains": [],
            "database_valid": None,
            "errors": [],
        }

        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                # Test zip integrity
                bad_file = zf.testzip()
                if bad_file:
                    result["valid"] = False
                    result["errors"].append(f"Corrupted file in archive: {bad_file}")
                    return result

                # Check contents
                result["contains"] = self._inspect_backup_contents(backup_path)

                # Verify database if present
                if "database" in result["contains"]:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_path = Path(temp_dir)
                        zf.extract("fuzzbin.db", temp_path)
                        db_path = temp_path / "fuzzbin.db"

                        try:
                            is_valid = await DatabaseBackup.verify_backup(db_path)
                            result["database_valid"] = is_valid
                            if not is_valid:
                                result["valid"] = False
                                result["errors"].append("Database integrity check failed")
                        except Exception as e:
                            result["database_valid"] = False
                            result["valid"] = False
                            result["errors"].append(f"Database verification error: {e}")

        except zipfile.BadZipFile as e:
            result["valid"] = False
            result["errors"].append(f"Invalid zip file: {e}")

        logger.info(
            "backup_verified",
            filename=filename,
            valid=result["valid"],
            contains=result["contains"],
        )

        return result

    def get_backup_path(self, filename: str) -> Path | None:
        """
        Get full path to a backup file.

        Args:
            filename: Backup filename

        Returns:
            Path to backup file, or None if not found
        """
        backup_path = self.backup_dir / filename
        if backup_path.exists() and backup_path.suffix == ".zip":
            return backup_path
        return None
