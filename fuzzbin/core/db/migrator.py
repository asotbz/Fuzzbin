"""Database migration manager."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import aiosqlite
import structlog

from .exceptions import MigrationError

logger = structlog.get_logger(__name__)


class Migrator:
    """Manages database schema migrations."""

    def __init__(self, db_path: Path, migrations_dir: Path, enable_wal: bool = True):
        """
        Initialize migrator.

        Args:
            db_path: Path to SQLite database file
            migrations_dir: Path to directory containing migration SQL files
            enable_wal: Whether to enable WAL mode (only used if no connection provided)
        """
        self.db_path = db_path
        self.migrations_dir = migrations_dir
        self.enable_wal = enable_wal

    async def run_migrations(self, connection: Optional[aiosqlite.Connection] = None) -> None:
        """
        Run all pending migrations.

        Args:
            connection: Optional existing database connection. If provided, uses this
                       connection instead of creating a new one. This avoids WAL mode
                       conflicts when the database is already open.

        Raises:
            MigrationError: If migration fails
        """
        if connection is not None:
            # Use provided connection (WAL already configured by caller)
            await self._run_migrations_with_connection(connection)
        else:
            # Create our own connection (standalone migration run)
            async with aiosqlite.connect(str(self.db_path)) as db:
                # Enable foreign keys
                await db.execute("PRAGMA foreign_keys = ON")

                # Enable WAL mode if configured
                if self.enable_wal:
                    await db.execute("PRAGMA journal_mode = WAL")

                await self._run_migrations_with_connection(db)

    async def _run_migrations_with_connection(self, db: aiosqlite.Connection) -> None:
        """Run migrations using the provided connection."""
        # Ensure schema_migrations table exists
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                filename TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
        """
        )
        await db.commit()

        # Get applied migrations
        applied = await self._get_applied_migrations(db)
        applied_versions = {v for v, _, _ in applied}

        # Get pending migrations
        pending = await self._get_pending_migrations(applied_versions)

        if not pending:
            logger.info("no_pending_migrations", db_path=str(self.db_path))
            return

        logger.info(
            "migrations_pending",
            count=len(pending),
            db_path=str(self.db_path),
        )

        # Apply each migration in order
        for version, filename, sql, checksum in pending:
            try:
                logger.info(
                    "migration_applying",
                    version=version,
                    filename=filename,
                )

                # Execute migration SQL
                await db.executescript(sql)

                # Record migration
                now = datetime.now(timezone.utc).isoformat()
                await db.execute(
                    """
                    INSERT INTO schema_migrations (version, filename, checksum, applied_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (version, filename, checksum, now),
                )
                await db.commit()

                logger.info(
                    "migration_applied",
                    version=version,
                    filename=filename,
                )

            except Exception as e:
                await db.rollback()
                logger.error(
                    "migration_failed",
                    version=version,
                    filename=filename,
                    error=str(e),
                )
                raise MigrationError(
                    f"Migration {filename} failed: {e}",
                    version=version,
                    filename=filename,
                ) from e

        logger.info(
            "migrations_complete",
            applied=len(pending),
            db_path=str(self.db_path),
        )

    async def _get_applied_migrations(self, db: aiosqlite.Connection) -> List[Tuple[int, str, str]]:
        """Get list of applied migrations."""
        cursor = await db.execute(
            "SELECT version, filename, checksum FROM schema_migrations ORDER BY version"
        )
        rows = await cursor.fetchall()
        return [(row[0], row[1], row[2]) for row in rows]

    async def _get_pending_migrations(
        self, applied_versions: set
    ) -> List[Tuple[int, str, str, str]]:
        """
        Get list of pending migrations.

        Returns:
            List of tuples: (version, filename, sql, checksum)
        """
        if not self.migrations_dir.exists():
            logger.warning(
                "migrations_dir_not_found",
                path=str(self.migrations_dir),
            )
            return []

        # Find all .sql files
        sql_files = sorted(self.migrations_dir.glob("*.sql"))

        pending = []
        for sql_file in sql_files:
            # Extract version from filename (e.g., "001_initial_schema.sql" -> 1)
            try:
                version_str = sql_file.stem.split("_")[0]
                version = int(version_str)
            except (IndexError, ValueError):
                logger.warning(
                    "migration_filename_invalid",
                    filename=sql_file.name,
                )
                continue

            # Skip if already applied
            if version in applied_versions:
                continue

            # Read SQL content
            try:
                sql = sql_file.read_text()
                checksum = self._calculate_checksum(sql)
                pending.append((version, sql_file.name, sql, checksum))
            except Exception as e:
                logger.error(
                    "migration_read_failed",
                    filename=sql_file.name,
                    error=str(e),
                )
                raise MigrationError(
                    f"Failed to read migration {sql_file.name}: {e}",
                    version=version,
                    filename=sql_file.name,
                ) from e

        # Sort by version
        pending.sort(key=lambda x: x[0])
        return pending

    def _calculate_checksum(self, content: str) -> str:
        """Calculate SHA-256 checksum of migration content."""
        return hashlib.sha256(content.encode()).hexdigest()
