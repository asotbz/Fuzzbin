"""Exceptions for database operations."""

from pathlib import Path
from typing import Optional


class DatabaseError(Exception):
    """Base exception for database errors."""

    pass


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""

    def __init__(self, message: str, path: Optional[Path] = None):
        super().__init__(message)
        self.path = path


class MigrationError(DatabaseError):
    """Raised when database migration fails."""

    def __init__(
        self,
        message: str,
        version: Optional[int] = None,
        filename: Optional[str] = None,
    ):
        super().__init__(message)
        self.version = version
        self.filename = filename


class VideoNotFoundError(DatabaseError):
    """Raised when a video record cannot be found."""

    def __init__(
        self,
        message: str,
        video_id: Optional[int] = None,
        imvdb_id: Optional[str] = None,
        youtube_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.video_id = video_id
        self.imvdb_id = imvdb_id
        self.youtube_id = youtube_id


class ArtistNotFoundError(DatabaseError):
    """Raised when an artist record cannot be found."""

    def __init__(
        self,
        message: str,
        artist_id: Optional[int] = None,
        name: Optional[str] = None,
    ):
        super().__init__(message)
        self.artist_id = artist_id
        self.name = name


class DuplicateRecordError(DatabaseError):
    """Raised when attempting to create a duplicate record."""

    def __init__(
        self,
        message: str,
        table: Optional[str] = None,
        key: Optional[str] = None,
        value: Optional[str] = None,
    ):
        super().__init__(message)
        self.table = table
        self.key = key
        self.value = value


class BackupError(DatabaseError):
    """Raised when database backup or restore operation fails."""

    def __init__(
        self,
        message: str,
        source_path: Optional[Path] = None,
        backup_path: Optional[Path] = None,
    ):
        super().__init__(message)
        self.source_path = source_path
        self.backup_path = backup_path


class QueryError(DatabaseError):
    """Raised when database query execution fails."""

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        params: Optional[tuple] = None,
    ):
        super().__init__(message)
        self.query = query
        self.params = params


class TransactionError(DatabaseError):
    """Raised when transaction operation fails."""

    def __init__(self, message: str, operation: Optional[str] = None):
        super().__init__(message)
        self.operation = operation


class CollectionNotFoundError(DatabaseError):
    """Raised when a collection record cannot be found."""

    def __init__(
        self,
        message: str,
        collection_id: Optional[int] = None,
        name: Optional[str] = None,
    ):
        super().__init__(message)
        self.collection_id = collection_id
        self.name = name


class TagNotFoundError(DatabaseError):
    """Raised when a tag record cannot be found."""

    def __init__(
        self,
        message: str,
        tag_id: Optional[int] = None,
        name: Optional[str] = None,
    ):
        super().__init__(message)
        self.tag_id = tag_id
        self.name = name
