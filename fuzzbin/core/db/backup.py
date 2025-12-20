"""Database backup and restore utilities."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List

import aiosqlite
import structlog

from .exceptions import BackupError

logger = structlog.get_logger(__name__)


class DatabaseBackup:
    """Utilities for database backup and restore operations."""

    @staticmethod
    async def backup(source_db: Path, backup_path: Path) -> None:
        """
        Create database backup.

        Args:
            source_db: Path to source database
            backup_path: Path for backup file

        Raises:
            BackupError: If backup fails
        """
        try:
            # Ensure backup directory exists
            backup_path.parent.mkdir(parents=True, exist_ok=True)

            # Connect to source database
            async with aiosqlite.connect(str(source_db)) as source_conn:
                # Connect to backup database
                async with aiosqlite.connect(str(backup_path)) as backup_conn:
                    # Perform backup using SQLite backup API
                    await source_conn.backup(backup_conn)

            logger.info(
                "database_backed_up",
                source_db=str(source_db),
                backup_path=str(backup_path),
                backup_size=backup_path.stat().st_size,
            )

        except Exception as e:
            logger.error(
                "backup_failed",
                source_db=str(source_db),
                backup_path=str(backup_path),
                error=str(e),
            )
            raise BackupError(
                f"Failed to backup database: {e}",
                source_path=source_db,
                backup_path=backup_path,
            ) from e

    @staticmethod
    async def restore(backup_path: Path, target_db: Path) -> None:
        """
        Restore database from backup.

        Args:
            backup_path: Path to backup file
            target_db: Path for restored database

        Raises:
            BackupError: If restore fails
        """
        if not backup_path.exists():
            raise BackupError(
                f"Backup file not found: {backup_path}",
                backup_path=backup_path,
            )

        try:
            # Ensure target directory exists
            target_db.parent.mkdir(parents=True, exist_ok=True)

            # Connect to backup database
            async with aiosqlite.connect(str(backup_path)) as backup_conn:
                # Connect to target database
                async with aiosqlite.connect(str(target_db)) as target_conn:
                    # Perform restore using SQLite backup API
                    await backup_conn.backup(target_conn)

            logger.info(
                "database_restored",
                backup_path=str(backup_path),
                target_db=str(target_db),
            )

        except Exception as e:
            logger.error(
                "restore_failed",
                backup_path=str(backup_path),
                target_db=str(target_db),
                error=str(e),
            )
            raise BackupError(
                f"Failed to restore database: {e}",
                source_path=backup_path,
                backup_path=target_db,
            ) from e

    @staticmethod
    async def verify_backup(backup_path: Path) -> bool:
        """
        Verify backup integrity.

        Args:
            backup_path: Path to backup file

        Returns:
            True if backup is valid

        Raises:
            BackupError: If verification fails
        """
        if not backup_path.exists():
            raise BackupError(
                f"Backup file not found: {backup_path}",
                backup_path=backup_path,
            )

        try:
            async with aiosqlite.connect(str(backup_path)) as conn:
                # Run integrity check
                cursor = await conn.execute("PRAGMA integrity_check")
                result = await cursor.fetchone()

                is_valid = result and result[0] == "ok"

                logger.info(
                    "backup_verified",
                    backup_path=str(backup_path),
                    is_valid=is_valid,
                )

                return is_valid

        except Exception as e:
            logger.error(
                "verification_failed",
                backup_path=str(backup_path),
                error=str(e),
            )
            raise BackupError(
                f"Failed to verify backup: {e}",
                backup_path=backup_path,
            ) from e

    @staticmethod
    def list_backups(backup_dir: Path) -> List[Dict[str, any]]:
        """
        List available backups in directory.

        Args:
            backup_dir: Directory containing backups

        Returns:
            List of backup metadata dicts with keys: path, size, timestamp

        Raises:
            BackupError: If directory access fails
        """
        if not backup_dir.exists():
            logger.warning("backup_dir_not_found", path=str(backup_dir))
            return []

        try:
            backups = []
            for backup_file in sorted(backup_dir.glob("*.db")):
                stat = backup_file.stat()
                backups.append(
                    {
                        "path": backup_file,
                        "size": stat.st_size,
                        "timestamp": datetime.fromtimestamp(stat.st_mtime),
                    }
                )

            logger.info("backups_listed", count=len(backups), path=str(backup_dir))
            return backups

        except Exception as e:
            logger.error(
                "list_backups_failed",
                path=str(backup_dir),
                error=str(e),
            )
            raise BackupError(
                f"Failed to list backups: {e}",
                source_path=backup_dir,
            ) from e
