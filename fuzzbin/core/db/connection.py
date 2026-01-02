"""Database connection management."""

from pathlib import Path
from typing import Any, Optional

import aiosqlite
import structlog

from .exceptions import DatabaseConnectionError

logger = structlog.get_logger(__name__)


class DatabaseConnection:
    """Manages async SQLite database connection with context manager support."""

    def __init__(
        self,
        db_path: Path,
        enable_wal: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize database connection manager.

        Args:
            db_path: Path to SQLite database file
            enable_wal: Enable Write-Ahead Logging mode
            timeout: Connection timeout in seconds
        """
        self.db_path = db_path
        self.enable_wal = enable_wal
        self.timeout = timeout
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> aiosqlite.Connection:
        """
        Establish database connection.

        Returns:
            Active database connection

        Raises:
            DatabaseConnectionError: If connection fails
        """
        if self._connection is not None:
            return self._connection

        try:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Connect to database
            self._connection = await aiosqlite.connect(
                str(self.db_path),
                timeout=self.timeout,
            )

            # Enable row factory for dict-like access
            self._connection.row_factory = aiosqlite.Row

            # Enable foreign key constraints
            await self._connection.execute("PRAGMA foreign_keys = ON")

            # Enable WAL mode for better concurrency
            if self.enable_wal:
                await self._connection.execute("PRAGMA journal_mode = WAL")

            logger.info(
                "database_connected",
                db_path=str(self.db_path),
                wal_mode=self.enable_wal,
            )

            return self._connection

        except Exception as e:
            logger.error(
                "database_connection_failed",
                db_path=str(self.db_path),
                error=str(e),
            )
            raise DatabaseConnectionError(
                f"Failed to connect to database: {e}",
                path=self.db_path,
            ) from e

    async def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            logger.info("database_closed", db_path=str(self.db_path))

    async def __aenter__(self) -> aiosqlite.Connection:
        """Context manager entry."""
        return await self.connect()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        await self.close()
