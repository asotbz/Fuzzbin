"""Database module for music video library management."""

from .backup import DatabaseBackup
from .connection import DatabaseConnection
from .exceptions import (
    ArtistNotFoundError,
    BackupError,
    DatabaseConnectionError,
    DatabaseError,
    DuplicateRecordError,
    MigrationError,
    QueryError,
    TransactionError,
    VideoNotFoundError,
)
from .exporter import NFOExporter
from .migrator import Migrator
from .query import VideoQuery
from .repository import VideoRepository

__all__ = [
    "VideoRepository",
    "VideoQuery",
    "NFOExporter",
    "DatabaseBackup",
    "DatabaseConnection",
    "Migrator",
    "DatabaseError",
    "DatabaseConnectionError",
    "MigrationError",
    "VideoNotFoundError",
    "ArtistNotFoundError",
    "DuplicateRecordError",
    "BackupError",
    "QueryError",
    "TransactionError",
]
