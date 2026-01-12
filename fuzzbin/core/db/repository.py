"""Video repository for database CRUD operations."""

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite
import structlog

from .connection import DatabaseConnection
from .exceptions import (
    ArtistNotFoundError,
    CollectionNotFoundError,
    QueryError,
    TagNotFoundError,
    TransactionError,
    VideoNotFoundError,
)
from .migrator import Migrator
from .query import VideoQuery

logger = structlog.get_logger(__name__)


class VideoRepository:
    """Repository for video metadata CRUD operations."""

    def __init__(
        self,
        db_path: Path,
        enable_wal: bool = True,
        timeout: int = 30,
        library_dir: Optional[Path] = None,
    ):
        """
        Initialize video repository.

        Args:
            db_path: Absolute path to SQLite database file
            enable_wal: Enable Write-Ahead Logging mode
            timeout: Connection timeout in seconds
            library_dir: Optional library directory for relative path calculation
        """
        self.db_path = db_path
        self.library_dir = library_dir
        self._db_connection = DatabaseConnection(db_path, enable_wal, timeout)
        self._connection: Optional[aiosqlite.Connection] = None

    # Default database configuration constants (not user-configurable)
    DEFAULT_DATABASE_PATH = "fuzzbin.db"
    DEFAULT_ENABLE_WAL = True
    DEFAULT_CONNECTION_TIMEOUT = 30

    @classmethod
    async def from_config(
        cls,
        config: Any,
        config_dir: Optional[Path] = None,
        library_dir: Optional[Path] = None,
    ) -> "VideoRepository":
        """
        Create repository from DatabaseConfig.

        Args:
            config: DatabaseConfig instance (currently unused, kept for API compatibility)
            config_dir: Config directory for resolving relative database_path.
                       If not provided, database_path must be absolute or
                       will be resolved relative to CWD.
            library_dir: Optional library directory for relative path calculation.

        Returns:
            Initialized VideoRepository
        """
        # Use hardcoded defaults - database settings are not user-configurable
        db_path = Path(cls.DEFAULT_DATABASE_PATH)
        if config_dir:
            db_path = config_dir / db_path

        # Ensure parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        repo = cls(
            db_path=db_path,
            enable_wal=cls.DEFAULT_ENABLE_WAL,
            timeout=cls.DEFAULT_CONNECTION_TIMEOUT,
            library_dir=library_dir,
        )

        # Connect and run migrations
        await repo.connect()

        # Run migrations using the existing connection to avoid WAL conflicts
        migrations_dir = Path(__file__).parent / "migrations"
        migrator = Migrator(db_path, migrations_dir, enable_wal=cls.DEFAULT_ENABLE_WAL)
        await migrator.run_migrations(connection=repo._connection)

        logger.info(
            "repository_initialized",
            db_path=str(db_path),
            library_dir=str(library_dir) if library_dir else None,
        )

        return repo

    async def connect(self) -> None:
        """Establish database connection."""
        if self._connection is None:
            self._connection = await self._db_connection.connect()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            await self._db_connection.close()
            self._connection = None

    async def __aenter__(self) -> "VideoRepository":
        """Context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        await self.close()

    @asynccontextmanager
    async def transaction(self) -> Any:
        """
        Explicit transaction context manager.

        Example:
            async with repository.transaction():
                await repository.create_video(...)
                await repository.link_video_artist(...)
        """
        if self._connection is None:
            raise TransactionError("No active connection", operation="begin")

        try:
            await self._connection.execute("BEGIN")
            logger.debug("transaction_started")
            yield
            await self._connection.commit()
            logger.debug("transaction_committed")
        except Exception as e:
            await self._connection.rollback()
            logger.error("transaction_rolled_back", error=str(e))
            raise TransactionError(f"Transaction failed: {e}", operation="rollback") from e

    def query(self) -> VideoQuery:
        """
        Create a new fluent query builder.

        Returns:
            VideoQuery instance for building queries

        Example:
            videos = await repository.query()\\
                .where_artist("Madonna")\\
                .where_year_range(1990, 2000)\\
                .order_by("year")\\
                .execute()
        """
        if self._connection is None:
            raise QueryError("No active connection")

        return VideoQuery(self._connection)

    # ==================== Video CRUD Methods ====================

    async def create_video(
        self,
        title: str,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        year: Optional[int] = None,
        director: Optional[str] = None,
        genre: Optional[str] = None,
        studio: Optional[str] = None,
        video_file_path: Optional[str] = None,
        nfo_file_path: Optional[str] = None,
        imvdb_video_id: Optional[str] = None,
        youtube_id: Optional[str] = None,
        vimeo_id: Optional[str] = None,
        status: str = "discovered",
        download_source: Optional[str] = None,
        **kwargs: Any,
    ) -> int:
        """
        Create a new video record.

        Args:
            title: Video title (required)
            artist: Primary artist name
            album: Album name
            year: Release year
            director: Director name
            genre: Music genre
            studio: Studio/label name
            video_file_path: Absolute path to video file
            nfo_file_path: Absolute path to NFO file
            imvdb_video_id: IMVDb video ID
            youtube_id: YouTube video ID
            vimeo_id: Vimeo video ID
            status: Initial status (default: discovered)
            download_source: Download source (youtube, vimeo, etc.)
            **kwargs: Additional fields (ignored)
            youtube_id: YouTube video ID
            vimeo_id: Vimeo video ID
            **kwargs: Additional fields (ignored)

        Returns:
            ID of created video record

        Raises:
            QueryError: If insert fails
        """
        if self._connection is None:
            raise QueryError("No active connection")

        now = datetime.now(timezone.utc).isoformat()

        # Calculate relative paths if library_dir is set
        video_rel_path = None
        nfo_rel_path = None
        if self.library_dir:
            if video_file_path:
                video_rel_path = self._get_relative_path(video_file_path)
            if nfo_file_path:
                nfo_rel_path = self._get_relative_path(nfo_file_path)

        try:
            cursor = await self._connection.execute(
                """
                INSERT INTO videos (
                    title, artist, album, year, director, genre, studio,
                    video_file_path, video_file_path_relative,
                    nfo_file_path, nfo_file_path_relative,
                    imvdb_video_id, youtube_id, vimeo_id,
                    status, status_changed_at, download_source,
                    created_at, updated_at, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    title,
                    artist,
                    album,
                    year,
                    director,
                    genre,
                    studio,
                    video_file_path,
                    video_rel_path,
                    nfo_file_path,
                    nfo_rel_path,
                    imvdb_video_id,
                    youtube_id,
                    vimeo_id,
                    status,
                    now,
                    download_source,
                    now,
                    now,
                ),
            )
            await self._connection.commit()

            video_id = cursor.lastrowid

            # Record initial status in history
            await self._add_status_history(
                video_id=video_id,
                old_status=None,
                new_status=status,
                reason="Initial creation",
                changed_by="create_video",
            )

            logger.info(
                "video_created",
                video_id=video_id,
                title=title,
                artist=artist,
                status=status,
            )

            return video_id

        except Exception as e:
            await self._connection.rollback()
            logger.error(
                "video_creation_failed",
                title=title,
                error=str(e),
            )
            raise QueryError(f"Failed to create video: {e}") from e

    async def get_video_by_id(self, video_id: int, include_deleted: bool = False) -> Dict[str, Any]:
        """
        Get video by ID.

        Args:
            video_id: Video ID
            include_deleted: Include soft-deleted records

        Returns:
            Video record as dictionary

        Raises:
            VideoNotFoundError: If video not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        where_clause = "WHERE id = ?"
        if not include_deleted:
            where_clause += " AND is_deleted = 0"

        cursor = await self._connection.execute(
            f"SELECT * FROM videos {where_clause}",
            (video_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise VideoNotFoundError(
                f"Video not found: {video_id}",
                video_id=video_id,
            )

        return dict(row)

    async def get_video_by_imvdb_id(
        self, imvdb_id: str, include_deleted: bool = False
    ) -> Dict[str, Any]:
        """
        Get video by IMVDb video ID.

        Args:
            imvdb_id: IMVDb video ID
            include_deleted: Include soft-deleted records

        Returns:
            Video record as dictionary

        Raises:
            VideoNotFoundError: If video not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        where_clause = "WHERE imvdb_video_id = ?"
        if not include_deleted:
            where_clause += " AND is_deleted = 0"

        cursor = await self._connection.execute(
            f"SELECT * FROM videos {where_clause}",
            (imvdb_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise VideoNotFoundError(
                f"Video not found with IMVDb ID: {imvdb_id}",
                imvdb_id=imvdb_id,
            )

        return dict(row)

    async def get_video_by_isrc(
        self, isrc: str, include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get video by ISRC code.

        Args:
            isrc: ISRC code
            include_deleted: Include soft-deleted records

        Returns:
            Video record as dictionary, or None if not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        where_clause = "WHERE isrc = ?"
        if not include_deleted:
            where_clause += " AND is_deleted = 0"

        cursor = await self._connection.execute(
            f"SELECT * FROM videos {where_clause}",
            (isrc,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return dict(row)

    async def get_video_by_musicbrainz_recording(
        self, mbid: str, include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get video by MusicBrainz recording MBID.

        Args:
            mbid: MusicBrainz recording MBID
            include_deleted: Include soft-deleted records

        Returns:
            Video record as dictionary, or None if not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        where_clause = "WHERE recording_mbid = ?"
        if not include_deleted:
            where_clause += " AND is_deleted = 0"

        cursor = await self._connection.execute(
            f"SELECT * FROM videos {where_clause}",
            (mbid,),
        )
        row = await cursor.fetchone()

        if not row:
            return None

        return dict(row)

    async def get_video_by_youtube_id(
        self, youtube_id: str, include_deleted: bool = False
    ) -> Dict[str, Any]:
        """
        Get video by YouTube video ID.

        Args:
            youtube_id: YouTube video ID
            include_deleted: Include soft-deleted records

        Returns:
            Video record as dictionary

        Raises:
            VideoNotFoundError: If video not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        where_clause = "WHERE youtube_id = ?"
        if not include_deleted:
            where_clause += " AND is_deleted = 0"

        cursor = await self._connection.execute(
            f"SELECT * FROM videos {where_clause}",
            (youtube_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise VideoNotFoundError(
                f"Video not found with YouTube ID: {youtube_id}",
                youtube_id=youtube_id,
            )

        return dict(row)

    async def update_video(self, video_id: int, **updates: Any) -> None:
        """
        Update video record.

        Args:
            video_id: Video ID
            **updates: Fields to update

        Raises:
            VideoNotFoundError: If video not found
            QueryError: If update fails
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify video exists and get current status
        # Include deleted videos - update should work on deleted records too
        # (e.g., when restoring from trash or updating paths during soft delete)
        current_video = await self.get_video_by_id(video_id, include_deleted=True)

        # Build update query
        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        # Calculate relative paths if updating file paths
        if self.library_dir:
            if "video_file_path" in updates:
                updates["video_file_path_relative"] = self._get_relative_path(
                    updates["video_file_path"]
                )
            if "nfo_file_path" in updates:
                updates["nfo_file_path_relative"] = self._get_relative_path(
                    updates["nfo_file_path"]
                )

        # Check if status is being changed
        status_changed = False
        old_status = None
        new_status = None

        if "status" in updates:
            new_status = updates["status"]
            old_status = current_video.get("status")
            status_changed = old_status != new_status

            if status_changed:
                updates["status_changed_at"] = now

        set_clause = ", ".join(f"{key} = ?" for key in updates.keys())
        values = list(updates.values())
        values.append(video_id)

        try:
            await self._connection.execute(
                f"UPDATE videos SET {set_clause} WHERE id = ?",
                values,
            )

            # Record status change in history if status changed
            if status_changed:
                await self._add_status_history(
                    video_id=video_id,
                    old_status=old_status,
                    new_status=new_status,
                    reason=updates.get("status_message", "Status updated via update_video"),
                    changed_by="update_video",
                )

            await self._connection.commit()

            logger.info(
                "video_updated",
                video_id=video_id,
                fields=list(updates.keys()),
                status_changed=status_changed,
            )

        except Exception as e:
            await self._connection.rollback()
            logger.error(
                "video_update_failed",
                video_id=video_id,
                error=str(e),
            )
            raise QueryError(f"Failed to update video: {e}") from e

    async def delete_video(self, video_id: int) -> None:
        """
        Soft delete video record.

        Args:
            video_id: Video ID

        Raises:
            VideoNotFoundError: If video not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify video exists
        await self.get_video_by_id(video_id)

        now = datetime.now(timezone.utc).isoformat()

        try:
            await self._connection.execute(
                "UPDATE videos SET is_deleted = 1, deleted_at = ? WHERE id = ?",
                (now, video_id),
            )
            await self._connection.commit()

            logger.info("video_soft_deleted", video_id=video_id)

        except Exception as e:
            await self._connection.rollback()
            logger.error(
                "video_soft_delete_failed",
                video_id=video_id,
                error=str(e),
            )
            raise QueryError(f"Failed to delete video: {e}") from e

    async def hard_delete_video(self, video_id: int) -> None:
        """
        Permanently delete video record.

        Args:
            video_id: Video ID

        Raises:
            VideoNotFoundError: If video not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify video exists (include deleted)
        await self.get_video_by_id(video_id, include_deleted=True)

        try:
            await self._connection.execute(
                "DELETE FROM videos WHERE id = ?",
                (video_id,),
            )
            await self._connection.commit()

            logger.info("video_hard_deleted", video_id=video_id)

        except Exception as e:
            await self._connection.rollback()
            logger.error(
                "video_hard_delete_failed",
                video_id=video_id,
                error=str(e),
            )
            raise QueryError(f"Failed to hard delete video: {e}") from e

    async def restore_video(self, video_id: int) -> None:
        """
        Restore soft-deleted video record.

        Args:
            video_id: Video ID

        Raises:
            VideoNotFoundError: If video not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify video exists (include deleted)
        video = await self.get_video_by_id(video_id, include_deleted=True)

        if not video.get("is_deleted"):
            logger.warning("video_not_deleted", video_id=video_id)
            return

        try:
            await self._connection.execute(
                "UPDATE videos SET is_deleted = 0, deleted_at = NULL WHERE id = ?",
                (video_id,),
            )
            await self._connection.commit()

            logger.info("video_restored", video_id=video_id)

        except Exception as e:
            await self._connection.rollback()
            logger.error(
                "video_restore_failed",
                video_id=video_id,
                error=str(e),
            )
            raise QueryError(f"Failed to restore video: {e}") from e

    async def get_deleted_videos(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get all soft-deleted video records.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of soft-deleted video records
        """
        if self._connection is None:
            raise QueryError("No active connection")

        sql = """
            SELECT v.*
            FROM videos v
            WHERE v.is_deleted = 1
            ORDER BY v.deleted_at DESC
        """

        if limit is not None:
            sql += f" LIMIT {limit} OFFSET {offset}"

        try:
            cursor = await self._connection.execute(sql)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("get_deleted_videos_failed", error=str(e))
            raise QueryError(f"Failed to get deleted videos: {e}") from e

    async def count_deleted_videos(self) -> int:
        """
        Count total number of soft-deleted videos.

        Returns:
            Count of soft-deleted videos
        """
        if self._connection is None:
            raise QueryError("No active connection")

        try:
            cursor = await self._connection.execute(
                "SELECT COUNT(*) FROM videos WHERE is_deleted = 1"
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
        except Exception as e:
            logger.error("count_deleted_videos_failed", error=str(e))
            raise QueryError(f"Failed to count deleted videos: {e}") from e

    async def search_videos(
        self, query: str, include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Full-text search for videos using FTS5.

        Args:
            query: FTS5 search query
            include_deleted: Include soft-deleted records

        Returns:
            List of matching video records

        Example:
            videos = await repo.search_videos("rock AND director:smith")
        """
        q = self.query().search(query)
        if include_deleted:
            q = q.include_deleted()

        return await q.execute()

    async def list_videos(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List all videos with optional pagination.

        Args:
            limit: Maximum number of videos to return
            offset: Number of videos to skip
            include_deleted: Include soft-deleted videos

        Returns:
            List of video dicts

        Example:
            >>> videos = await repo.list_videos(limit=100, offset=0)
            >>> for video in videos:
            ...     print(video['title'])
        """
        q = self.query()

        if not include_deleted:
            q = q.where_not_deleted()

        if limit:
            q = q.limit(limit).offset(offset)

        return await q.execute()

    # ==================== Artist CRUD Methods ====================

    async def upsert_artist(
        self,
        name: str,
        imvdb_entity_id: Optional[str] = None,
        discogs_artist_id: Optional[int] = None,
        biography: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> int:
        """
        Insert or update artist record.

        Args:
            name: Artist name (required)
            imvdb_entity_id: IMVDb entity ID
            discogs_artist_id: Discogs artist ID
            biography: Artist biography
            image_url: Artist image URL

        Returns:
            Artist ID

        Raises:
            QueryError: If operation fails
        """
        if self._connection is None:
            raise QueryError("No active connection")

        now = datetime.now(timezone.utc).isoformat()

        try:
            # Try to find existing artist
            cursor = await self._connection.execute(
                "SELECT id FROM artists WHERE name = ? AND is_deleted = 0",
                (name,),
            )
            row = await cursor.fetchone()

            if row:
                # Update existing
                artist_id = row[0]
                updates = {"updated_at": now}
                if imvdb_entity_id is not None:
                    updates["imvdb_entity_id"] = imvdb_entity_id
                if discogs_artist_id is not None:
                    updates["discogs_artist_id"] = discogs_artist_id
                if biography is not None:
                    updates["biography"] = biography
                if image_url is not None:
                    updates["image_url"] = image_url

                set_clause = ", ".join(f"{key} = ?" for key in updates.keys())
                values = list(updates.values())
                values.append(artist_id)

                await self._connection.execute(
                    f"UPDATE artists SET {set_clause} WHERE id = ?",
                    values,
                )
                await self._connection.commit()

                logger.info("artist_updated", artist_id=artist_id, name=name)
            else:
                # Insert new
                cursor = await self._connection.execute(
                    """
                    INSERT INTO artists (
                        name, imvdb_entity_id, discogs_artist_id,
                        biography, image_url,
                        created_at, updated_at, is_deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        name,
                        imvdb_entity_id,
                        discogs_artist_id,
                        biography,
                        image_url,
                        now,
                        now,
                    ),
                )
                await self._connection.commit()
                artist_id = cursor.lastrowid

                logger.info("artist_created", artist_id=artist_id, name=name)

            return artist_id

        except Exception as e:
            await self._connection.rollback()
            logger.error(
                "artist_upsert_failed",
                name=name,
                error=str(e),
            )
            raise QueryError(f"Failed to upsert artist: {e}") from e

    async def get_artist_by_id(
        self, artist_id: int, include_deleted: bool = False
    ) -> Dict[str, Any]:
        """
        Get artist by ID.

        Args:
            artist_id: Artist ID
            include_deleted: Include soft-deleted records

        Returns:
            Artist record as dictionary

        Raises:
            ArtistNotFoundError: If artist not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        where_clause = "WHERE id = ?"
        if not include_deleted:
            where_clause += " AND is_deleted = 0"

        cursor = await self._connection.execute(
            f"SELECT * FROM artists {where_clause}",
            (artist_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise ArtistNotFoundError(
                f"Artist not found: {artist_id}",
                artist_id=artist_id,
            )

        return dict(row)

    async def list_artists(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        List all artists.

        Args:
            include_deleted: Include soft-deleted artists

        Returns:
            List of artist dicts
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = "SELECT * FROM artists"

        if not include_deleted:
            query += " WHERE is_deleted = 0"

        query += " ORDER BY name"

        cursor = await self._connection.execute(query)
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def update_artist(self, artist_id: int, **updates: Any) -> None:
        """
        Update artist record.

        Args:
            artist_id: Artist ID
            **updates: Fields to update

        Raises:
            QueryError: If artist not found or update fails

        Example:
            >>> await repo.update_artist(1, biography="New bio", image_url="http://...")
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify artist exists
        await self.get_artist_by_id(artist_id)

        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        set_clause = ", ".join(f"{key} = ?" for key in updates.keys())
        values = list(updates.values())
        values.append(artist_id)

        await self._connection.execute(
            f"UPDATE artists SET {set_clause} WHERE id = ?",
            values,
        )
        await self._connection.commit()

    async def soft_delete_artist(self, artist_id: int) -> None:
        """
        Soft delete artist record.

        Args:
            artist_id: Artist ID

        Raises:
            QueryError: If artist not found

        Example:
            >>> await repo.soft_delete_artist(1)
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify artist exists
        await self.get_artist_by_id(artist_id)

        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            "UPDATE artists SET is_deleted = 1, deleted_at = ? WHERE id = ?",
            (now, artist_id),
        )
        await self._connection.commit()

    async def get_artist_videos(
        self,
        artist_id: int,
        role: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get all videos for an artist.

        Args:
            artist_id: Artist ID
            role: Optional role filter ('primary' or 'featured')
            include_deleted: Include soft-deleted videos

        Returns:
            List of video dicts with role and position

        Example:
            >>> videos = await repo.get_artist_videos(1, role="primary")
            >>> for video in videos:
            ...     print(f"{video['title']} - {video['role']}")
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = """
            SELECT v.*, va.role, va.position
            FROM videos v
            JOIN video_artists va ON v.id = va.video_id
            WHERE va.artist_id = ?
        """
        params = [artist_id]

        if not include_deleted:
            query += " AND v.is_deleted = 0"

        if role:
            query += " AND va.role = ?"
            params.append(role)

        query += " ORDER BY v.year DESC, v.title"

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    # ==================== Video-Artist Relationship Methods ====================

    async def link_video_artist(
        self,
        video_id: int,
        artist_id: int,
        role: str = "primary",
        position: int = 0,
    ) -> None:
        """
        Link video to artist.

        Args:
            video_id: Video ID
            artist_id: Artist ID
            role: Artist role ('primary' or 'featured')
            position: Position for ordering (0-based)

        Raises:
            QueryError: If link fails
        """
        if self._connection is None:
            raise QueryError("No active connection")

        if role not in ("primary", "featured"):
            raise ValueError(f"Invalid role: {role}")

        try:
            await self._connection.execute(
                """
                INSERT OR IGNORE INTO video_artists (video_id, artist_id, role, position)
                VALUES (?, ?, ?, ?)
                """,
                (video_id, artist_id, role, position),
            )
            await self._connection.commit()

            logger.info(
                "video_artist_linked",
                video_id=video_id,
                artist_id=artist_id,
                role=role,
            )

        except Exception as e:
            await self._connection.rollback()
            logger.error(
                "video_artist_link_failed",
                video_id=video_id,
                artist_id=artist_id,
                error=str(e),
            )
            raise QueryError(f"Failed to link video and artist: {e}") from e

    async def unlink_all_video_artists(self, video_id: int) -> int:
        """
        Remove all artist links for a video.

        Used for re-enrichment to clear existing links before re-linking.

        Args:
            video_id: Video ID

        Returns:
            Number of links deleted

        Raises:
            QueryError: If operation fails
        """
        if self._connection is None:
            raise QueryError("No active connection")

        try:
            cursor = await self._connection.execute(
                "DELETE FROM video_artists WHERE video_id = ?",
                (video_id,),
            )
            await self._connection.commit()

            deleted_count = cursor.rowcount
            logger.info(
                "video_artists_unlinked",
                video_id=video_id,
                deleted_count=deleted_count,
            )

            return deleted_count

        except Exception as e:
            await self._connection.rollback()
            logger.error(
                "unlink_video_artists_failed",
                video_id=video_id,
                error=str(e),
            )
            raise QueryError(f"Failed to unlink video artists: {e}") from e

    async def unlink_video_artist(
        self,
        video_id: int,
        artist_id: int,
    ) -> None:
        """
        Remove link between a video and a specific artist.

        Args:
            video_id: Video ID
            artist_id: Artist ID to unlink

        Example:
            >>> await repo.unlink_video_artist(video_id=1, artist_id=5)
        """
        if self._connection is None:
            raise QueryError("No active connection")

        await self._connection.execute(
            "DELETE FROM video_artists WHERE video_id = ? AND artist_id = ?",
            (video_id, artist_id),
        )
        await self._connection.commit()

    async def get_video_artists(
        self, video_id: int, role: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get artists for a video.

        Args:
            video_id: Video ID
            role: Optional role filter ('primary' or 'featured')

        Returns:
            List of artist records with role and position
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = """
            SELECT a.*, va.role, va.position
            FROM artists a
            JOIN video_artists va ON a.id = va.artist_id
            WHERE va.video_id = ? AND a.is_deleted = 0
        """
        params = [video_id]

        if role:
            query += " AND va.role = ?"
            params.append(role)

        query += " ORDER BY va.position"

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    # ==================== Collection CRUD Methods ====================

    async def upsert_collection(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> int:
        """
        Create or update a collection.

        Args:
            name: Collection name (unique)
            description: Optional description

        Returns:
            Collection ID
        """
        if self._connection is None:
            raise QueryError("No active connection")

        now = datetime.now(timezone.utc).isoformat()

        # Try to get existing collection
        cursor = await self._connection.execute(
            "SELECT id FROM collections WHERE LOWER(name) = LOWER(? ) AND is_deleted = 0",
            (name,),
        )
        row = await cursor.fetchone()

        if row:
            # Update existing
            collection_id = row[0]
            await self._connection.execute(
                """
                UPDATE collections 
                SET description = ?, updated_at = ?
                WHERE id = ?
                """,
                (description, now, collection_id),
            )
        else:
            # Insert new
            cursor = await self._connection.execute(
                """
                INSERT INTO collections (name, description, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (name, description, now, now),
            )
            collection_id = cursor.lastrowid

        await self._connection.commit()
        return collection_id

    async def get_collection_by_id(
        self, collection_id: int, include_deleted: bool = False
    ) -> Dict[str, Any]:
        """
        Get collection by ID.

        Args:
            collection_id: Collection ID
            include_deleted: Include soft-deleted collections

        Returns:
            Collection dict

        Raises:
            QueryError: If collection not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = "SELECT * FROM collections WHERE id = ?"
        params = [collection_id]

        if not include_deleted:
            query += " AND is_deleted = 0"

        cursor = await self._connection.execute(query, params)
        row = await cursor.fetchone()

        if not row:
            raise CollectionNotFoundError(
                f"Collection {collection_id} not found",
                collection_id=collection_id,
            )

        return dict(row)

    async def list_collections(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        List all collections.

        Args:
            include_deleted: Include soft-deleted collections

        Returns:
            List of collection dicts
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = "SELECT * FROM collections"

        if not include_deleted:
            query += " WHERE is_deleted = 0"

        query += " ORDER BY name"

        cursor = await self._connection.execute(query)
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def update_collection(self, collection_id: int, **updates: Any) -> None:
        """
        Update collection record.

        Args:
            collection_id: Collection ID
            **updates: Fields to update

        Raises:
            QueryError: If collection not found or update fails

        Example:
            >>> await repo.update_collection(1, description="Updated description")
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify collection exists
        await self.get_collection_by_id(collection_id)

        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        set_clause = ", ".join(f"{key} = ?" for key in updates.keys())
        values = list(updates.values())
        values.append(collection_id)

        await self._connection.execute(
            f"UPDATE collections SET {set_clause} WHERE id = ?",
            values,
        )
        await self._connection.commit()

    async def soft_delete_collection(self, collection_id: int) -> None:
        """
        Soft delete collection.

        Args:
            collection_id: Collection ID

        Raises:
            QueryError: If collection not found

        Example:
            >>> await repo.soft_delete_collection(1)
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify collection exists
        await self.get_collection_by_id(collection_id)

        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            "UPDATE collections SET is_deleted = 1, deleted_at = ? WHERE id = ?",
            (now, collection_id),
        )
        await self._connection.commit()

    # ==================== Video-Collection Relationship Methods ====================

    async def link_video_collection(
        self,
        video_id: int,
        collection_id: int,
        position: int = 0,
    ) -> None:
        """
        Link a video to a collection.

        Args:
            video_id: Video ID
            collection_id: Collection ID
            position: Position in collection (for ordering)
        """
        if self._connection is None:
            raise QueryError("No active connection")

        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """
            INSERT OR IGNORE INTO video_collections 
            (video_id, collection_id, position, added_at)
            VALUES (?, ?, ?, ?)
            """,
            (video_id, collection_id, position, now),
        )
        await self._connection.commit()

    async def get_video_collections(self, video_id: int) -> List[Dict[str, Any]]:
        """
        Get all collections for a video.

        Args:
            video_id: Video ID

        Returns:
            List of collection dicts with position
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = """
            SELECT c.*, vc.position, vc.added_at
            FROM collections c
            JOIN video_collections vc ON c.id = vc.collection_id
            WHERE vc.video_id = ? AND c.is_deleted = 0
            ORDER BY c.name
        """

        cursor = await self._connection.execute(query, (video_id,))
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def get_collection_videos(
        self, collection_id: int, order_by_position: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all videos in a collection.

        Args:
            collection_id: Collection ID
            order_by_position: Order by position in collection (default: True)

        Returns:
            List of video dicts with position
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = """
            SELECT v.*, vc.position, vc.added_at
            FROM videos v
            JOIN video_collections vc ON v.id = vc.video_id
            WHERE vc.collection_id = ? AND v.is_deleted = 0
        """

        if order_by_position:
            query += " ORDER BY vc.position, v.title"
        else:
            query += " ORDER BY v.title"

        cursor = await self._connection.execute(query, (collection_id,))
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def remove_video_from_collection(
        self,
        video_id: int,
        collection_id: int,
    ) -> None:
        """
        Remove video from collection.

        Args:
            video_id: Video ID
            collection_id: Collection ID to remove from

        Example:
            >>> await repo.remove_video_from_collection(video_id=1, collection_id=2)
        """
        if self._connection is None:
            raise QueryError("No active connection")

        await self._connection.execute(
            "DELETE FROM video_collections WHERE video_id = ? AND collection_id = ?",
            (video_id, collection_id),
        )
        await self._connection.commit()

    # ==================== Tag CRUD Methods ====================

    async def upsert_tag(
        self,
        name: str,
        normalize: bool = True,
    ) -> int:
        """
        Create or get a tag.

        Args:
            name: Tag name
            normalize: Normalize tag name to lowercase (default: True)

        Returns:
            Tag ID
        """
        if self._connection is None:
            raise QueryError("No active connection")

        now = datetime.now(timezone.utc).isoformat()
        normalized_name = name.lower() if normalize else name

        # Try to get existing tag by normalized name
        cursor = await self._connection.execute(
            "SELECT id FROM tags WHERE normalized_name = ?",
            (normalized_name,),
        )
        row = await cursor.fetchone()

        if row:
            return row[0]

        # Insert new tag
        cursor = await self._connection.execute(
            """
            INSERT INTO tags (name, normalized_name, created_at)
            VALUES (?, ?, ?)
            """,
            (name, normalized_name, now),
        )
        tag_id = cursor.lastrowid
        await self._connection.commit()

        return tag_id

    async def get_tag_by_id(self, tag_id: int) -> Dict[str, Any]:
        """
        Get tag by ID.

        Args:
            tag_id: Tag ID

        Returns:
            Tag dict

        Raises:
            QueryError: If tag not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        cursor = await self._connection.execute(
            "SELECT * FROM tags WHERE id = ?",
            (tag_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise TagNotFoundError(
                f"Tag {tag_id} not found",
                tag_id=tag_id,
            )

        return dict(row)

    async def list_tags(
        self, min_usage_count: int = 0, order_by: str = "name"
    ) -> List[Dict[str, Any]]:
        """
        List all tags.

        Args:
            min_usage_count: Minimum usage count (default: 0)
            order_by: Sort order - 'name' or 'usage_count' (default: 'name')

        Returns:
            List of tag dicts
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = "SELECT * FROM tags WHERE usage_count >= ?"

        if order_by == "usage_count":
            query += " ORDER BY usage_count DESC, name"
        else:
            query += " ORDER BY name"

        cursor = await self._connection.execute(query, (min_usage_count,))
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def delete_tag(self, tag_id: int) -> None:
        """
        Delete a tag (hard delete).

        Args:
            tag_id: Tag ID

        Raises:
            QueryError: If tag not found

        Example:
            >>> await repo.delete_tag(1)
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify tag exists
        await self.get_tag_by_id(tag_id)

        # Delete tag (cascade will remove video_tags entries)
        await self._connection.execute(
            "DELETE FROM tags WHERE id = ?",
            (tag_id,),
        )
        await self._connection.commit()

    async def set_video_tags(
        self,
        video_id: int,
        tag_names: List[str],
        source: str = "manual",
        replace_existing: bool = True,
    ) -> None:
        """
        Set tags on a video, optionally replacing existing ones.

        Args:
            video_id: Video ID
            tag_names: List of tag names to add
            source: Tag source ('manual' or 'auto')
            replace_existing: Replace existing tags (default: True)

        Example:
            >>> await repo.set_video_tags(1, ["rock", "80s"], source="auto")
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify video exists
        await self.get_video_by_id(video_id)

        # Remove existing tags if replacing
        if replace_existing:
            await self._connection.execute(
                "DELETE FROM video_tags WHERE video_id = ?",
                (video_id,),
            )

        # Add new tags
        for tag_name in tag_names:
            tag_id = await self.upsert_tag(tag_name)
            await self.add_video_tag(video_id, tag_id, source=source)

    async def get_videos_by_tag(self, tag_name: str) -> List[Dict[str, Any]]:
        """
        Get all videos with a specific tag name.

        Args:
            tag_name: Tag name

        Returns:
            List of video dicts

        Example:
            >>> videos = await repo.get_videos_by_tag("rock")
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Normalize tag name for lookup
        normalized_name = tag_name.lower().strip()

        query = """
            SELECT v.*, vt.source, vt.added_at
            FROM videos v
            JOIN video_tags vt ON v.id = vt.video_id
            JOIN tags t ON vt.tag_id = t.id
            WHERE t.name = ? AND v.is_deleted = 0
            ORDER BY v.title
        """

        cursor = await self._connection.execute(query, (normalized_name,))
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    # ==================== Video-Tag Relationship Methods ====================

    async def add_video_tag(
        self,
        video_id: int,
        tag_id: int,
        source: str = "manual",
    ) -> None:
        """
        Add a tag to a video.

        Args:
            video_id: Video ID
            tag_id: Tag ID
            source: Tag source ('manual' or 'auto')
        """
        if self._connection is None:
            raise QueryError("No active connection")

        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """
            INSERT OR IGNORE INTO video_tags 
            (video_id, tag_id, added_at, source)
            VALUES (?, ?, ?, ?)
            """,
            (video_id, tag_id, now, source),
        )
        await self._connection.commit()

    async def remove_video_tag(
        self,
        video_id: int,
        tag_id: int,
    ) -> None:
        """
        Remove a tag from a video.

        Args:
            video_id: Video ID
            tag_id: Tag ID
        """
        if self._connection is None:
            raise QueryError("No active connection")

        await self._connection.execute(
            "DELETE FROM video_tags WHERE video_id = ? AND tag_id = ?",
            (video_id, tag_id),
        )
        await self._connection.commit()

    async def get_video_tags(self, video_id: int) -> List[Dict[str, Any]]:
        """
        Get all tags for a video.

        Args:
            video_id: Video ID

        Returns:
            List of tag dicts with source and added_at
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = """
            SELECT t.*, vt.source, vt.added_at
            FROM tags t
            JOIN video_tags vt ON t.id = vt.tag_id
            WHERE vt.video_id = ?
            ORDER BY t.name
        """

        cursor = await self._connection.execute(query, (video_id,))
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def get_tag_videos(self, tag_id: int) -> List[Dict[str, Any]]:
        """
        Get all videos with a specific tag.

        Args:
            tag_id: Tag ID

        Returns:
            List of video dicts
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = """
            SELECT v.*, vt.source, vt.added_at
            FROM videos v
            JOIN video_tags vt ON v.id = vt.video_id
            WHERE vt.tag_id = ? AND v.is_deleted = 0
            ORDER BY v.title
        """

        cursor = await self._connection.execute(query, (tag_id,))
        rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    async def auto_add_decade_tag(
        self,
        video_id: int,
        year: int,
        tag_format: str = "{decade}s",
    ) -> Optional[int]:
        """
        Automatically add a decade tag based on video year.

        Args:
            video_id: Video ID
            year: Video release year
            tag_format: Format string for decade tag (default: "{decade}s")

        Returns:
            Tag ID if tag was added, None if year is invalid

        Example:
            >>> await repo.auto_add_decade_tag(video_id=1, year=1991)
            # Creates and adds "90s" tag
        """
        if not year or year < 1900 or year > 2100:
            return None

        # Calculate decade (e.g., 1991 -> 90, 2005 -> 0, 2010 -> 10)
        decade = (year // 10) % 10 * 10

        # For 2000-2009, use "00s" or similar based on format
        if year >= 2000 and year < 2010:
            decade = 0

        tag_name = tag_format.format(decade=str(decade).zfill(2))

        tag_id = await self.upsert_tag(tag_name, normalize=True)
        await self.add_video_tag(video_id, tag_id, source="auto")

        return tag_id

    async def remove_auto_decade_tags(
        self,
        video_id: int,
        old_format: Optional[str] = None,
    ) -> int:
        """
        Remove auto-generated decade tags from a video.

        This method removes decade tags that were automatically added
        (source='auto'). Can optionally filter by specific format pattern.

        Args:
            video_id: Video ID
            old_format: Optional format pattern to match (e.g., "{decade}s")
                       If None, removes all decade-like tags with source='auto'

        Returns:
            Number of tags removed

        Example:
            >>> await repo.remove_auto_decade_tags(video_id=1)
            # Removes "90s", "00s", "10s" etc. with source='auto'
            >>> await repo.remove_auto_decade_tags(video_id=1, old_format="decade-{decade}")
            # Removes only "decade-90", "decade-00" etc. with source='auto'
        """
        import re

        async with self._connection.execute(
            """
            SELECT t.id, t.name
            FROM tags t
            JOIN video_tags vt ON t.id = vt.tag_id
            WHERE vt.video_id = ? AND vt.source = 'auto'
            """,
            (video_id,),
        ) as cursor:
            auto_tags = await cursor.fetchall()

        if not auto_tags:
            return 0

        # Build regex pattern to match decade tags
        if old_format:
            # Convert format string to regex pattern
            # e.g., "{decade}s" -> "^\d{2}s$"
            # e.g., "decade-{decade}" -> "^decade-\d{2}$"
            pattern = old_format.replace("{decade}", r"\d{2}")
            pattern = "^" + re.escape(pattern).replace(r"\\d\{2\}", r"\d{2}") + "$"
        else:
            # Default pattern matches common decade formats
            # Matches: "90s", "00s", "decade-90", "1990s", etc.
            pattern = r"^(\d{2}s?|decade-\d{2}|\d{4}s?)$"

        removed_count = 0
        for tag_id, tag_name in auto_tags:
            if re.match(pattern, tag_name, re.IGNORECASE):
                await self.remove_video_tag(video_id, tag_id)
                removed_count += 1

        return removed_count

    async def update_decade_tag(
        self,
        video_id: int,
        old_year: Optional[int],
        new_year: int,
        tag_format: str = "{decade}s",
    ) -> bool:
        """
        Atomically update decade tag when video year changes.

        Removes old decade tag (if year changed) and adds new decade tag.
        Uses transaction to ensure atomicity.

        Args:
            video_id: Video ID
            old_year: Previous year value (None if no previous year)
            new_year: New year value
            tag_format: Format string for decade tag

        Returns:
            True if tag was updated, False if years are in same decade

        Example:
            >>> await repo.update_decade_tag(video_id=1, old_year=1991, new_year=2006)
            # Removes "90s", adds "00s"
        """
        if not new_year or new_year < 1900 or new_year > 2100:
            return False

        # Calculate decades
        old_decade = None
        if old_year and 1900 <= old_year <= 2100:
            old_decade = (old_year // 10) % 10 * 10
            if old_year >= 2000 and old_year < 2010:
                old_decade = 0

        new_decade = (new_year // 10) % 10 * 10
        if new_year >= 2000 and new_year < 2010:
            new_decade = 0

        # If decades are the same, no update needed
        if old_decade == new_decade:
            return False

        async with self.transaction():
            # Remove old decade tag if it exists
            if old_decade is not None:
                old_tag_name = tag_format.format(decade=str(old_decade).zfill(2))
                # Find and remove the specific decade tag
                async with self._connection.execute(
                    """
                    SELECT t.id
                    FROM tags t
                    JOIN video_tags vt ON t.id = vt.tag_id
                    WHERE vt.video_id = ? AND t.name = ? AND vt.source = 'auto'
                    """,
                    (video_id, old_tag_name),
                ) as cursor:
                    result = await cursor.fetchone()
                    if result:
                        await self.remove_video_tag(video_id, result[0])

            # Add new decade tag
            await self.auto_add_decade_tag(video_id, new_year, tag_format)

        return True

    # ==================== Status Management Methods ====================

    async def update_status(
        self,
        video_id: int,
        new_status: str,
        reason: Optional[str] = None,
        changed_by: Optional[str] = None,
        status_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update video status and record in history.

        Args:
            video_id: Video ID
            new_status: New status value
            reason: Reason for status change
            changed_by: Component/user that changed status
            status_message: Optional status message (e.g., error details)
            metadata: Additional metadata to store in history

        Raises:
            VideoNotFoundError: If video not found
            ValueError: If status is invalid
        """
        valid_statuses = {
            "discovered",
            "queued",
            "downloading",
            "downloaded",
            "imported",
            "organized",
            "missing",
            "failed",
            "archived",
        }

        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}. Must be one of {valid_statuses}")

        # Get current video to check old status
        video = await self.get_video_by_id(video_id)
        old_status = video.get("status")

        if old_status == new_status:
            logger.debug("status_unchanged", video_id=video_id, status=new_status)
            return

        now = datetime.now(timezone.utc).isoformat()

        if self._connection is None:
            raise RuntimeError("Database connection not initialized")

        try:
            # Update video status
            await self._connection.execute(
                """
                UPDATE videos 
                SET status = ?, status_changed_at = ?, status_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_status, now, status_message, now, video_id),
            )

            # Record in history
            await self._add_status_history(
                video_id=video_id,
                old_status=old_status,
                new_status=new_status,
                reason=reason,
                changed_by=changed_by,
                metadata=metadata,
            )

            logger.info(
                "status_updated",
                video_id=video_id,
                old_status=old_status,
                new_status=new_status,
                reason=reason,
            )

        except Exception as e:
            if self._connection is not None:
                await self._connection.rollback()
            logger.error(
                "status_update_failed",
                video_id=video_id,
                error=str(e),
            )
            raise QueryError(f"Failed to update status: {e}") from e

    async def get_status_history(
        self, video_id: int, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get status change history for a video.

        Args:
            video_id: Video ID
            limit: Optional limit on number of history entries

        Returns:
            List of status history records (newest first)
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = """
            SELECT * FROM video_status_history
            WHERE video_id = ?
            ORDER BY changed_at DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor = await self._connection.execute(query, (video_id,))
        rows = await cursor.fetchall()

        results = []
        for row in rows:
            record = dict(row)
            # Deserialize metadata if present
            if record.get("metadata"):
                record["metadata"] = self._deserialize_json(record["metadata"])
            results.append(record)

        return results

    # ==================== FFProbe Integration Methods ====================

    async def analyze_video_file(
        self,
        video_id: int,
        file_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Analyze video file and update metadata fields.

        Extracts technical metadata from video file using ffprobe and updates
        the database with: duration, resolution, codecs, bitrate, frame rate,
        audio channels, sample rate, aspect ratio, and container format.

        Args:
            video_id: Video ID
            file_path: Optional explicit file path (if None, uses video_file_path from database)

        Returns:
            Dictionary of extracted metadata fields

        Raises:
            ValueError: If ffprobe client not set
            VideoNotFoundError: If video not found
            FileNotFoundError: If video file doesn't exist
            FFProbeError: If ffprobe execution or parsing fails

        Example:
            >>> repo.set_ffprobe_client(ffprobe_client)
            >>> metadata = await repo.analyze_video_file(video_id)
            >>> print(f"Resolution: {metadata['width']}x{metadata['height']}")
            >>> print(f"Duration: {metadata['duration']}s")
        """
        if not hasattr(self, "_ffprobe_client") or self._ffprobe_client is None:
            raise ValueError("FFProbe client not set. Call set_ffprobe_client() first.")

        # Import here to avoid circular dependency
        from ..parsers.ffprobe_parser import FFProbeParser

        # Get video record
        video = await self.get_video_by_id(video_id)

        # Determine file path
        if file_path is None:
            file_path_str = video.get("video_file_path")
            if not file_path_str:
                raise ValueError(f"Video {video_id} has no file path and none was provided")
            file_path = Path(file_path_str)

        if not file_path.exists():
            raise FileNotFoundError(f"Video file not found: {file_path}")

        logger.info(
            "analyzing_video_file",
            video_id=video_id,
            file_path=str(file_path),
        )

        # Extract metadata using ffprobe
        media_info = await self._ffprobe_client.get_media_info(file_path)
        metadata = FFProbeParser.extract_video_metadata(media_info)

        # Update video record with metadata
        await self.update_video(video_id, **metadata)

        logger.info(
            "video_analysis_complete",
            video_id=video_id,
            duration=metadata.get("duration"),
            resolution=(
                f"{metadata.get('width')}x{metadata.get('height')}"
                if metadata.get("width")
                else None
            ),
            video_codec=metadata.get("video_codec"),
            audio_codec=metadata.get("audio_codec"),
        )

        return metadata

    # ==================== Helper Methods ====================

    async def _add_status_history(
        self,
        video_id: int,
        old_status: Optional[str],
        new_status: str,
        reason: Optional[str] = None,
        changed_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add entry to status history (internal method)."""
        now = datetime.now(timezone.utc).isoformat()
        metadata_json = self._serialize_json(metadata) if metadata else None

        if self._connection is None:
            raise RuntimeError("Database connection not initialized")

        await self._connection.execute(
            """
            INSERT INTO video_status_history 
            (video_id, old_status, new_status, changed_at, reason, changed_by, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (video_id, old_status, new_status, now, reason, changed_by, metadata_json),
        )
        await self._connection.commit()

    def _get_relative_path(self, absolute_path: str) -> Optional[str]:
        """Calculate relative path from workspace root."""
        if not self.library_dir or not absolute_path:
            return None

        try:
            abs_path = Path(absolute_path)
            return str(abs_path.relative_to(self.library_dir))
        except (ValueError, TypeError):
            return None

    def _serialize_json(self, data: Any) -> str:
        """Serialize data to JSON string."""
        return json.dumps(data, ensure_ascii=False)

    def _deserialize_json(self, json_str: Optional[str]) -> Any:
        """Deserialize JSON string to data."""
        if not json_str:
            return None
        return json.loads(json_str)

    # ==================== Bulk Operations (Phase 7) ====================

    async def bulk_update_videos(
        self,
        video_ids: List[int],
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update multiple videos in a single transaction.

        Args:
            video_ids: List of video IDs to update
            updates: Fields to update for all videos

        Returns:
            Dict with 'success_ids', 'failed_ids', and 'errors'

        Example:
            result = await repo.bulk_update_videos(
                video_ids=[1, 2, 3],
                updates={"genre": "Rock", "studio": "Universal"}
            )
        """
        result: dict[str, Any] = {"success_ids": [], "failed_ids": [], "errors": {}}

        if not video_ids:
            return result

        async with self.transaction():
            for video_id in video_ids:
                try:
                    await self.update_video(video_id, **updates)
                    result["success_ids"].append(video_id)
                except VideoNotFoundError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)
                except QueryError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)

        logger.info(
            "bulk_videos_updated",
            total=len(video_ids),
            success=len(result["success_ids"]),
            failed=len(result["failed_ids"]),
        )
        return result

    async def bulk_delete_videos(
        self,
        video_ids: List[int],
        hard_delete: bool = False,
    ) -> Dict[str, Any]:
        """
        Delete multiple videos in a single transaction.

        Args:
            video_ids: List of video IDs to delete
            hard_delete: If True, permanently delete; if False, soft delete

        Returns:
            Dict with 'success_ids', 'failed_ids', and 'errors'
        """
        result: dict[str, Any] = {"success_ids": [], "failed_ids": [], "errors": {}}

        if not video_ids:
            return result

        async with self.transaction():
            for video_id in video_ids:
                try:
                    if hard_delete:
                        await self.hard_delete_video(video_id)
                    else:
                        await self.delete_video(video_id)
                    result["success_ids"].append(video_id)
                except VideoNotFoundError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)
                except QueryError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)

        logger.info(
            "bulk_videos_deleted",
            total=len(video_ids),
            success=len(result["success_ids"]),
            failed=len(result["failed_ids"]),
            hard_delete=hard_delete,
        )
        return result

    async def bulk_update_status(
        self,
        video_ids: List[int],
        new_status: str,
        reason: Optional[str] = None,
        changed_by: Optional[str] = "bulk_update_status",
    ) -> Dict[str, Any]:
        """
        Update status for multiple videos in a single transaction.

        Args:
            video_ids: List of video IDs
            new_status: New status to set
            reason: Reason for status change
            changed_by: Component/user making the change

        Returns:
            Dict with 'success_ids', 'failed_ids', and 'errors'
        """
        result: dict[str, Any] = {"success_ids": [], "failed_ids": [], "errors": {}}

        if not video_ids:
            return result

        async with self.transaction():
            for video_id in video_ids:
                try:
                    await self.update_status(
                        video_id=video_id,
                        new_status=new_status,
                        reason=reason,
                        changed_by=changed_by,
                    )
                    result["success_ids"].append(video_id)
                except (VideoNotFoundError, ValueError) as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)
                except QueryError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)

        logger.info(
            "bulk_status_updated",
            total=len(video_ids),
            success=len(result["success_ids"]),
            failed=len(result["failed_ids"]),
            new_status=new_status,
        )
        return result

    async def bulk_apply_tags(
        self,
        video_ids: List[int],
        tag_names: List[str],
        replace: bool = False,
    ) -> Dict[str, Any]:
        """
        Apply tags to multiple videos in a single transaction.

        Args:
            video_ids: List of video IDs
            tag_names: List of tag names to apply
            replace: If True, replace existing tags; if False, add to existing

        Returns:
            Dict with 'success_ids', 'failed_ids', and 'errors'
        """
        result: dict[str, Any] = {"success_ids": [], "failed_ids": [], "errors": {}}

        if not video_ids or not tag_names:
            return result

        # First, ensure all tags exist and get their IDs
        tag_ids = []
        for tag_name in tag_names:
            tag_id = await self.upsert_tag(tag_name)
            tag_ids.append(tag_id)

        now = datetime.now(timezone.utc).isoformat()

        async with self.transaction():
            for video_id in video_ids:
                try:
                    # Verify video exists
                    await self.get_video_by_id(video_id)

                    if self._connection is None:
                        raise RuntimeError("Database connection not initialized")

                    if replace:
                        # Remove existing tags
                        await self._connection.execute(
                            "DELETE FROM video_tags WHERE video_id = ?",
                            (video_id,),
                        )

                    # Add new tags
                    for tag_id in tag_ids:
                        await self._connection.execute(
                            """
                            INSERT OR IGNORE INTO video_tags 
                            (video_id, tag_id, added_at, source)
                            VALUES (?, ?, ?, 'manual')
                            """,
                            (video_id, tag_id, now),
                        )

                    result["success_ids"].append(video_id)
                except VideoNotFoundError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)
                except QueryError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)

        logger.info(
            "bulk_tags_applied",
            total=len(video_ids),
            success=len(result["success_ids"]),
            failed=len(result["failed_ids"]),
            tags=tag_names,
            replace=replace,
        )
        return result

    async def bulk_add_to_collection(
        self,
        video_ids: List[int],
        collection_id: int,
    ) -> Dict[str, Any]:
        """
        Add multiple videos to a collection in a single transaction.

        Args:
            video_ids: List of video IDs
            collection_id: Collection ID to add videos to

        Returns:
            Dict with 'success_ids', 'failed_ids', and 'errors'
        """
        result: dict[str, Any] = {"success_ids": [], "failed_ids": [], "errors": {}}

        if not video_ids:
            return result

        # Verify collection exists
        try:
            await self.get_collection_by_id(collection_id)
        except CollectionNotFoundError as e:
            for video_id in video_ids:
                result["failed_ids"].append(video_id)
                result["errors"][video_id] = str(e)
            return result

        async with self.transaction():
            for video_id in video_ids:
                try:
                    await self.link_video_collection(video_id, collection_id)
                    result["success_ids"].append(video_id)
                except VideoNotFoundError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)
                except QueryError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)

        logger.info(
            "bulk_added_to_collection",
            total=len(video_ids),
            success=len(result["success_ids"]),
            failed=len(result["failed_ids"]),
            collection_id=collection_id,
        )
        return result

    async def bulk_organize_videos(
        self,
        video_updates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Update file paths for multiple videos (used after file organization).

        Args:
            video_updates: List of dicts with 'video_id', 'video_file_path',
                          and optionally 'nfo_file_path'

        Returns:
            Dict with 'success_ids', 'failed_ids', and 'errors'

        Example:
            result = await repo.bulk_organize_videos([
                {"video_id": 1, "video_file_path": "/new/path/video.mp4"},
                {"video_id": 2, "video_file_path": "/new/path/video2.mp4", "nfo_file_path": "/new/path/video2.nfo"},
            ])
        """
        result: dict[str, Any] = {"success_ids": [], "failed_ids": [], "errors": {}}

        if not video_updates:
            return result

        async with self.transaction():
            for update in video_updates:
                video_id = update.get("video_id")
                if not video_id:
                    continue

                updates = {}
                if "video_file_path" in update:
                    updates["video_file_path"] = update["video_file_path"]
                if "nfo_file_path" in update:
                    updates["nfo_file_path"] = update["nfo_file_path"]

                if not updates:
                    continue

                try:
                    await self.update_video(video_id, **updates)
                    result["success_ids"].append(video_id)
                except VideoNotFoundError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)
                except QueryError as e:
                    result["failed_ids"].append(video_id)
                    result["errors"][video_id] = str(e)

        logger.info(
            "bulk_videos_organized",
            total=len(video_updates),
            success=len(result["success_ids"]),
            failed=len(result["failed_ids"]),
        )
        return result

    # ==================== Faceted Search (Phase 7) ====================

    async def get_facets(
        self,
        include_deleted: bool = False,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get faceted counts for filtering UI.

        Returns counts by tag, genre, year, and director for building
        filter UIs with counts.

        Args:
            include_deleted: Include soft-deleted videos in counts

        Returns:
            Dict with 'tags', 'genres', 'years', 'directors' facets,
            each containing list of {'value': str, 'count': int}
        """
        if self._connection is None:
            raise QueryError("No active connection")

        deleted_filter = "" if include_deleted else "AND v.is_deleted = 0"
        none_facet_value = "__none__"

        facets: dict[str, list[Any]] = {
            "tags": [],
            "genres": [],
            "years": [],
            "directors": [],
        }

        # Tag facets
        cursor = await self._connection.execute(
            f"""
            SELECT t.name, COUNT(DISTINCT vt.video_id) as count
            FROM tags t
            JOIN video_tags vt ON t.id = vt.tag_id
            JOIN videos v ON vt.video_id = v.id
            WHERE 1=1 {deleted_filter}
            GROUP BY t.name
            ORDER BY count DESC, t.name
            """,
        )
        rows = await cursor.fetchall()
        facets["tags"] = [{"value": row["name"], "count": row["count"]} for row in rows]

        cursor = await self._connection.execute(
            f"""
            SELECT COUNT(*) as count
            FROM videos v
            WHERE 1=1 {deleted_filter}
            AND NOT EXISTS (
                SELECT 1 FROM video_tags vt
                WHERE vt.video_id = v.id
            )
            """,
        )
        row = await cursor.fetchone()
        missing_tag_count = row["count"] if row else 0
        if missing_tag_count:
            facets["tags"] = [{"value": none_facet_value, "count": missing_tag_count}] + facets[
                "tags"
            ]

        # Genre facets
        cursor = await self._connection.execute(
            f"""
            SELECT genre, COUNT(*) as count
            FROM videos v
            WHERE genre IS NOT NULL AND genre != '' {deleted_filter}
            GROUP BY genre
            ORDER BY count DESC, genre
            """,
        )
        rows = await cursor.fetchall()
        facets["genres"] = [{"value": row["genre"], "count": row["count"]} for row in rows]

        cursor = await self._connection.execute(
            f"""
            SELECT COUNT(*) as count
            FROM videos v
            WHERE (genre IS NULL OR genre = '') {deleted_filter}
            """,
        )
        row = await cursor.fetchone()
        missing_genre_count = row["count"] if row else 0
        if missing_genre_count:
            facets["genres"] = [{"value": none_facet_value, "count": missing_genre_count}] + facets[
                "genres"
            ]

        # Year facets
        cursor = await self._connection.execute(
            f"""
            SELECT year, COUNT(*) as count
            FROM videos v
            WHERE year IS NOT NULL {deleted_filter}
            GROUP BY year
            ORDER BY year DESC
            """,
        )
        rows = await cursor.fetchall()
        facets["years"] = [{"value": str(row["year"]), "count": row["count"]} for row in rows]

        cursor = await self._connection.execute(
            f"""
            SELECT COUNT(*) as count
            FROM videos v
            WHERE year IS NULL {deleted_filter}
            """,
        )
        row = await cursor.fetchone()
        missing_year_count = row["count"] if row else 0
        if missing_year_count:
            facets["years"] = [{"value": none_facet_value, "count": missing_year_count}] + facets[
                "years"
            ]

        # Director facets
        cursor = await self._connection.execute(
            f"""
            SELECT director, COUNT(*) as count
            FROM videos v
            WHERE director IS NOT NULL AND director != '' {deleted_filter}
            GROUP BY director
            ORDER BY count DESC, director
            """,
        )
        rows = await cursor.fetchall()
        facets["directors"] = [{"value": row["director"], "count": row["count"]} for row in rows]

        cursor = await self._connection.execute(
            f"""
            SELECT COUNT(*) as count
            FROM videos v
            WHERE (director IS NULL OR director = '') {deleted_filter}
            """,
        )
        row = await cursor.fetchone()
        missing_director_count = row["count"] if row else 0
        if missing_director_count:
            facets["directors"] = [
                {"value": none_facet_value, "count": missing_director_count}
            ] + facets["directors"]

        logger.debug(
            "facets_retrieved",
            tag_count=len(facets["tags"]),
            genre_count=len(facets["genres"]),
            year_count=len(facets["years"]),
            director_count=len(facets["directors"]),
        )

        return facets

    # ==================== Saved Searches (Phase 7) ====================

    async def create_saved_search(
        self,
        name: str,
        query_json: str,
        description: Optional[str] = None,
    ) -> int:
        """
        Create a saved search.

        Args:
            name: Name for the saved search
            query_json: JSON-serialized search/filter parameters
            description: Optional description

        Returns:
            Created saved search ID
        """
        if self._connection is None:
            raise QueryError("No active connection")

        now = datetime.now(timezone.utc).isoformat()

        try:
            cursor = await self._connection.execute(
                """
                INSERT INTO saved_searches (name, description, query_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, description, query_json, now, now),
            )
            await self._connection.commit()
            search_id = cursor.lastrowid

            logger.info("saved_search_created", search_id=search_id, name=name)
            return search_id

        except Exception as e:
            await self._connection.rollback()
            logger.error("saved_search_creation_failed", name=name, error=str(e))
            raise QueryError(f"Failed to create saved search: {e}") from e

    async def get_saved_searches(self) -> List[Dict[str, Any]]:
        """
        Get all saved searches.

        Returns:
            List of saved search records
        """
        if self._connection is None:
            raise QueryError("No active connection")

        cursor = await self._connection.execute(
            """
            SELECT * FROM saved_searches
            ORDER BY created_at DESC
            """,
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_saved_search_by_id(self, search_id: int) -> Dict[str, Any]:
        """
        Get saved search by ID.

        Args:
            search_id: Saved search ID

        Returns:
            Saved search record

        Raises:
            QueryError: If not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        cursor = await self._connection.execute(
            "SELECT * FROM saved_searches WHERE id = ?",
            (search_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise QueryError(f"Saved search not found: {search_id}")

        return dict(row)

    async def delete_saved_search(self, search_id: int) -> None:
        """
        Delete a saved search.

        Args:
            search_id: Saved search ID to delete
        """
        if self._connection is None:
            raise QueryError("No active connection")

        try:
            cursor = await self._connection.execute(
                "DELETE FROM saved_searches WHERE id = ?",
                (search_id,),
            )
            await self._connection.commit()

            if cursor.rowcount == 0:
                raise QueryError(f"Saved search not found: {search_id}")

            logger.info("saved_search_deleted", search_id=search_id)

        except Exception as e:
            await self._connection.rollback()
            if "not found" in str(e):
                raise
            logger.error("saved_search_deletion_failed", search_id=search_id, error=str(e))
            raise QueryError(f"Failed to delete saved search: {e}") from e

    # ==================== Scheduled Tasks (Phase 7) ====================

    async def create_scheduled_task(
        self,
        name: str,
        job_type: str,
        cron_expression: str,
        description: Optional[str] = None,
        metadata_json: Optional[str] = None,
        enabled: bool = True,
    ) -> int:
        """
        Create a scheduled task.

        Args:
            name: Unique name for the task
            job_type: JobType enum value
            cron_expression: Cron expression for scheduling
            description: Optional description
            metadata_json: Optional JSON metadata for job handler
            enabled: Whether task is enabled

        Returns:
            Created task ID
        """
        if self._connection is None:
            raise QueryError("No active connection")

        now = datetime.now(timezone.utc).isoformat()

        # Calculate next run time
        from fuzzbin.tasks.queue import parse_cron

        next_run = parse_cron(cron_expression, datetime.now(timezone.utc))
        next_run_str = next_run.isoformat() if next_run else None

        try:
            cursor = await self._connection.execute(
                """
                INSERT INTO scheduled_tasks 
                (name, description, job_type, cron_expression, enabled, metadata_json, 
                 next_run_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    description,
                    job_type,
                    cron_expression,
                    1 if enabled else 0,
                    metadata_json,
                    next_run_str,
                    now,
                    now,
                ),
            )
            await self._connection.commit()
            task_id = cursor.lastrowid

            logger.info(
                "scheduled_task_created",
                task_id=task_id,
                name=name,
                job_type=job_type,
                cron=cron_expression,
            )
            return task_id

        except Exception as e:
            await self._connection.rollback()
            logger.error("scheduled_task_creation_failed", name=name, error=str(e))
            raise QueryError(f"Failed to create scheduled task: {e}") from e

    async def get_scheduled_tasks(
        self,
        enabled_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get all scheduled tasks.

        Args:
            enabled_only: Only return enabled tasks

        Returns:
            List of scheduled task records
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = "SELECT * FROM scheduled_tasks"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY name"

        cursor = await self._connection.execute(query)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_scheduled_task_by_id(self, task_id: int) -> Dict[str, Any]:
        """
        Get scheduled task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task record

        Raises:
            QueryError: If not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        cursor = await self._connection.execute(
            "SELECT * FROM scheduled_tasks WHERE id = ?",
            (task_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise QueryError(f"Scheduled task not found: {task_id}")

        return dict(row)

    async def update_scheduled_task(
        self,
        task_id: int,
        **updates: Any,
    ) -> None:
        """
        Update a scheduled task.

        Args:
            task_id: Task ID
            **updates: Fields to update (enabled, cron_expression, etc.)
        """
        if self._connection is None:
            raise QueryError("No active connection")

        # Verify exists
        await self.get_scheduled_task_by_id(task_id)

        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        # Recalculate next_run if cron changed
        if "cron_expression" in updates:
            from fuzzbin.tasks.queue import parse_cron

            next_run = parse_cron(updates["cron_expression"], datetime.now(timezone.utc))
            updates["next_run_at"] = next_run.isoformat() if next_run else None

        set_clause = ", ".join(f"{key} = ?" for key in updates.keys())
        values = list(updates.values())
        values.append(task_id)

        try:
            await self._connection.execute(
                f"UPDATE scheduled_tasks SET {set_clause} WHERE id = ?",
                values,
            )
            await self._connection.commit()

            logger.info("scheduled_task_updated", task_id=task_id, fields=list(updates.keys()))

        except Exception as e:
            await self._connection.rollback()
            logger.error("scheduled_task_update_failed", task_id=task_id, error=str(e))
            raise QueryError(f"Failed to update scheduled task: {e}") from e

    async def delete_scheduled_task(self, task_id: int) -> None:
        """
        Delete a scheduled task.

        Args:
            task_id: Task ID to delete
        """
        if self._connection is None:
            raise QueryError("No active connection")

        try:
            cursor = await self._connection.execute(
                "DELETE FROM scheduled_tasks WHERE id = ?",
                (task_id,),
            )
            await self._connection.commit()

            if cursor.rowcount == 0:
                raise QueryError(f"Scheduled task not found: {task_id}")

            logger.info("scheduled_task_deleted", task_id=task_id)

        except Exception as e:
            await self._connection.rollback()
            if "not found" in str(e):
                raise
            logger.error("scheduled_task_deletion_failed", task_id=task_id, error=str(e))
            raise QueryError(f"Failed to delete scheduled task: {e}") from e
