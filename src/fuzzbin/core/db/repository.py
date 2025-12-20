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
        workspace_root: Optional[Path] = None,
        enable_wal: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize video repository.

        Args:
            db_path: Path to SQLite database file
            workspace_root: Optional workspace root for relative path calculation
            enable_wal: Enable Write-Ahead Logging mode
            timeout: Connection timeout in seconds
        """
        self.db_path = db_path
        self.workspace_root = workspace_root
        self._db_connection = DatabaseConnection(db_path, enable_wal, timeout)
        self._connection: Optional[aiosqlite.Connection] = None

    @classmethod
    async def from_config(cls, config) -> "VideoRepository":
        """
        Create repository from DatabaseConfig.

        Args:
            config: DatabaseConfig instance

        Returns:
            Initialized VideoRepository
        """
        db_path = Path(config.database_path)
        workspace_root = Path(config.workspace_root) if config.workspace_root else None

        repo = cls(
            db_path=db_path,
            workspace_root=workspace_root,
            enable_wal=config.enable_wal_mode,
            timeout=config.connection_timeout,
        )

        # Connect and run migrations
        await repo.connect()

        # Run migrations
        migrations_dir = Path(__file__).parent / "migrations"
        migrator = Migrator(db_path, migrations_dir, enable_wal=config.enable_wal_mode)
        await migrator.run_migrations()

        logger.info(
            "repository_initialized",
            db_path=str(db_path),
            workspace_root=str(workspace_root) if workspace_root else None,
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

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        await self.close()

    @asynccontextmanager
    async def transaction(self):
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
        **kwargs,
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

        # Calculate relative paths if workspace_root is set
        video_rel_path = None
        nfo_rel_path = None
        if self.workspace_root:
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

    async def bulk_create_videos(self, videos: List[Dict[str, Any]]) -> List[int]:
        """
        Create multiple video records in a single transaction.

        Args:
            videos: List of video data dictionaries

        Returns:
            List of created video IDs

        Raises:
            QueryError: If bulk insert fails
        """
        if not videos:
            return []

        video_ids = []
        async with self.transaction():
            for video_data in videos:
                video_id = await self.create_video(**video_data)
                video_ids.append(video_id)

        logger.info("bulk_videos_created", count=len(video_ids))
        return video_ids

    async def get_video_by_id(
        self, video_id: int, include_deleted: bool = False
    ) -> Dict[str, Any]:
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

    async def get_video_by_path(
        self, file_path: str, include_deleted: bool = False
    ) -> Dict[str, Any]:
        """
        Get video by file path.

        Args:
            file_path: Video file path (absolute or relative)
            include_deleted: Include soft-deleted records

        Returns:
            Video record as dictionary

        Raises:
            VideoNotFoundError: If video not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        where_clause = "WHERE (video_file_path = ? OR video_file_path_relative = ?)"
        if not include_deleted:
            where_clause += " AND is_deleted = 0"

        cursor = await self._connection.execute(
            f"SELECT * FROM videos {where_clause}",
            (file_path, file_path),
        )
        row = await cursor.fetchone()

        if not row:
            raise VideoNotFoundError(
                f"Video not found with path: {file_path}",
            )

        return dict(row)

    async def update_video(self, video_id: int, **updates) -> None:
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
        current_video = await self.get_video_by_id(video_id)

        # Build update query
        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        # Calculate relative paths if updating file paths
        if self.workspace_root:
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

    async def get_artist_by_name(
        self, name: str, include_deleted: bool = False
    ) -> Dict[str, Any]:
        """
        Get artist by name.

        Args:
            name: Artist name
            include_deleted: Include soft-deleted records

        Returns:
            Artist record as dictionary

        Raises:
            ArtistNotFoundError: If artist not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        where_clause = "WHERE name = ?"
        if not include_deleted:
            where_clause += " AND is_deleted = 0"

        cursor = await self._connection.execute(
            f"SELECT * FROM artists {where_clause}",
            (name,),
        )
        row = await cursor.fetchone()

        if not row:
            raise ArtistNotFoundError(
                f"Artist not found: {name}",
                name=name,
            )

        return dict(row)

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

    async def bulk_link_artists(
        self,
        video_id: int,
        artist_links: List[Dict[str, Any]],
    ) -> None:
        """
        Link multiple artists to a video in a single transaction.

        Args:
            video_id: Video ID
            artist_links: List of dicts with keys: artist_id, role, position

        Example:
            await repo.bulk_link_artists(
                video_id=1,
                artist_links=[
                    {"artist_id": 10, "role": "primary", "position": 0},
                    {"artist_id": 20, "role": "featured", "position": 1},
                ]
            )

        Raises:
            QueryError: If bulk link fails
        """
        if not artist_links:
            return

        async with self.transaction():
            for link in artist_links:
                await self.link_video_artist(
                    video_id=video_id,
                    artist_id=link["artist_id"],
                    role=link.get("role", "primary"),
                    position=link.get("position", 0),
                )

        logger.info(
            "bulk_artists_linked",
            video_id=video_id,
            count=len(artist_links),
        )

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

    async def get_collection_by_name(
        self, name: str, include_deleted: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get collection by name.

        Args:
            name: Collection name
            include_deleted: Include soft-deleted collections

        Returns:
            Collection dict or None if not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        query = "SELECT * FROM collections WHERE LOWER(name) = LOWER(?)"
        params = [name]

        if not include_deleted:
            query += " AND is_deleted = 0"

        cursor = await self._connection.execute(query, params)
        row = await cursor.fetchone()

        return dict(row) if row else None

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

    async def delete_collection(self, collection_id: int) -> None:
        """
        Soft delete a collection.

        Args:
            collection_id: Collection ID
        """
        if self._connection is None:
            raise QueryError("No active connection")

        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """
            UPDATE collections 
            SET is_deleted = 1, deleted_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, collection_id),
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

    async def unlink_video_collection(
        self,
        video_id: int,
        collection_id: int,
    ) -> None:
        """
        Unlink a video from a collection.

        Args:
            video_id: Video ID
            collection_id: Collection ID
        """
        if self._connection is None:
            raise QueryError("No active connection")

        await self._connection.execute(
            "DELETE FROM video_collections WHERE video_id = ? AND collection_id = ?",
            (video_id, collection_id),
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

    async def get_tag_by_name(
        self, name: str, normalize: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Get tag by name.

        Args:
            name: Tag name
            normalize: Normalize tag name to lowercase (default: True)

        Returns:
            Tag dict or None if not found
        """
        if self._connection is None:
            raise QueryError("No active connection")

        normalized_name = name.lower() if normalize else name

        cursor = await self._connection.execute(
            "SELECT * FROM tags WHERE normalized_name = ?",
            (normalized_name,),
        )
        row = await cursor.fetchone()

        return dict(row) if row else None

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

    async def bulk_add_video_tags(
        self,
        video_id: int,
        tag_names: List[str],
        source: str = "manual",
        normalize: bool = True,
    ) -> List[int]:
        """
        Add multiple tags to a video (creates tags if needed).

        Args:
            video_id: Video ID
            tag_names: List of tag names
            source: Tag source ('manual' or 'auto')
            normalize: Normalize tag names to lowercase (default: True)

        Returns:
            List of tag IDs
        """
        if self._connection is None:
            raise QueryError("No active connection")

        tag_ids = []
        
        async with self.transaction():
            for tag_name in tag_names:
                tag_id = await self.upsert_tag(tag_name, normalize=normalize)
                await self.add_video_tag(video_id, tag_id, source=source)
                tag_ids.append(tag_id)

        return tag_ids

    async def replace_video_tags(
        self,
        video_id: int,
        tag_names: List[str],
        source: str = "manual",
        normalize: bool = True,
    ) -> List[int]:
        """
        Replace all tags for a video.

        Args:
            video_id: Video ID
            tag_names: List of tag names
            source: Tag source ('manual' or 'auto')
            normalize: Normalize tag names to lowercase (default: True)

        Returns:
            List of tag IDs
        """
        if self._connection is None:
            raise QueryError("No active connection")

        async with self.transaction():
            # Remove all existing tags
            await self._connection.execute(
                "DELETE FROM video_tags WHERE video_id = ?",
                (video_id,),
            )
            
            # Add new tags
            tag_ids = []
            for tag_name in tag_names:
                tag_id = await self.upsert_tag(tag_name, normalize=normalize)
                await self.add_video_tag(video_id, tag_id, source=source)
                tag_ids.append(tag_id)

        return tag_ids

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
            "discovered", "queued", "downloading", "downloaded",
            "imported", "organized", "missing", "failed", "archived"
        }
        
        if new_status not in valid_statuses:
            raise ValueError(
                f"Invalid status: {new_status}. Must be one of {valid_statuses}"
            )

        # Get current video to check old status
        video = await self.get_video_by_id(video_id)
        old_status = video.get("status")

        if old_status == new_status:
            logger.debug("status_unchanged", video_id=video_id, status=new_status)
            return

        now = datetime.now(timezone.utc).isoformat()

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

    async def mark_as_downloaded(
        self,
        video_id: int,
        file_path: str,
        file_size: Optional[int] = None,
        file_checksum: Optional[str] = None,
        download_source: Optional[str] = None,
    ) -> None:
        """
        Mark video as downloaded with file metadata.

        Args:
            video_id: Video ID
            file_path: Path to downloaded file
            file_size: File size in bytes
            file_checksum: SHA256 checksum
            download_source: Download source (youtube, vimeo, etc.)
        """
        now = datetime.now(timezone.utc).isoformat()
        
        # Calculate relative path if workspace_root is set
        rel_path = self._get_relative_path(file_path) if self.workspace_root else None

        updates = {
            "status": "downloaded",
            "status_changed_at": now,
            "video_file_path": file_path,
            "file_verified_at": now,
            "updated_at": now,
        }
        
        if rel_path:
            updates["video_file_path_relative"] = rel_path
        if file_size is not None:
            updates["file_size"] = file_size
        if file_checksum:
            updates["file_checksum"] = file_checksum
        if download_source:
            updates["download_source"] = download_source

        await self.update_video(video_id, **updates)
        
        await self.update_status(
            video_id,
            "downloaded",
            reason="File downloaded successfully",
            changed_by="mark_as_downloaded",
            metadata={
                "file_size": file_size,
                "file_checksum": file_checksum,
                "download_source": download_source,
            },
        )

        logger.info(
            "video_marked_downloaded",
            video_id=video_id,
            file_path=file_path,
            file_size=file_size,
        )

        # Automatically analyze video file if FFProbe client is set
        if hasattr(self, "_ffprobe_client") and self._ffprobe_client is not None:
            try:
                await self.analyze_video_file(video_id, file_path=Path(file_path))
            except Exception as e:
                # Log warning but don't fail the download marking
                logger.warning(
                    "video_analysis_failed",
                    video_id=video_id,
                    file_path=file_path,
                    error=str(e),
                    error_type=type(e).__name__,
                )

    async def mark_download_failed(
        self,
        video_id: int,
        error_message: str,
        increment_attempts: bool = True,
    ) -> None:
        """
        Mark video download as failed.

        Args:
            video_id: Video ID
            error_message: Error description
            increment_attempts: Whether to increment download_attempts counter
        """
        now = datetime.now(timezone.utc).isoformat()
        
        video = await self.get_video_by_id(video_id)
        attempts = video.get("download_attempts", 0)
        
        if increment_attempts:
            attempts += 1

        await self.update_video(
            video_id,
            status="failed",
            status_changed_at=now,
            status_message=error_message,
            last_download_error=error_message,
            last_download_attempt_at=now,
            download_attempts=attempts,
        )

        await self.update_status(
            video_id,
            "failed",
            reason=f"Download failed: {error_message}",
            changed_by="mark_download_failed",
            metadata={"error": error_message, "attempts": attempts},
        )

        logger.warning(
            "video_download_failed",
            video_id=video_id,
            error=error_message,
            attempts=attempts,
        )

    async def check_missing_files(self) -> List[Dict[str, Any]]:
        """
        Check for videos marked as downloaded but with missing files.

        Returns:
            List of videos with missing files
        """
        videos = await self.query().where_status("downloaded").execute()
        
        missing = []
        for video in videos:
            file_path = video.get("video_file_path")
            if file_path and not Path(file_path).exists():
                missing.append(video)
                
                # Update status to missing
                await self.update_status(
                    video["id"],
                    "missing",
                    reason="File no longer exists at expected path",
                    changed_by="check_missing_files",
                    metadata={"expected_path": file_path},
                )

        logger.info(
            "missing_files_checked",
            total_downloaded=len(videos),
            missing_count=len(missing),
        )

        return missing

    async def verify_file(
        self, video_id: int, calculate_checksum: bool = False
    ) -> bool:
        """
        Verify video file exists and optionally check checksum.

        Args:
            video_id: Video ID
            calculate_checksum: Whether to calculate and verify checksum

        Returns:
            True if file is valid
        """
        video = await self.get_video_by_id(video_id)
        file_path = video.get("video_file_path")
        
        if not file_path:
            return False
            
        path = Path(file_path)
        if not path.exists():
            await self.update_status(
                video_id,
                "missing",
                reason="File verification failed: file not found",
                changed_by="verify_file",
            )
            return False

        # Update file size and verification time
        file_size = path.stat().st_size
        now = datetime.now(timezone.utc).isoformat()
        
        await self.update_video(
            video_id,
            file_size=file_size,
            file_verified_at=now,
        )

        # TODO: Optionally calculate and verify checksum
        if calculate_checksum and video.get("file_checksum"):
            # Import hashlib and verify checksum
            pass

        logger.info(
            "file_verified",
            video_id=video_id,
            file_path=file_path,
            file_size=file_size,
        )

        return True

    # ==================== FFProbe Integration Methods ====================

    def set_ffprobe_client(self, client: Optional["FFProbeClient"]) -> None:
        """
        Set FFProbe client for video file analysis.

        This allows external initialization of the FFProbe client to avoid
        coupling the database layer to FFProbe configuration.

        Args:
            client: FFProbeClient instance or None to disable auto-analysis

        Example:
            >>> from fuzzbin.clients.ffprobe_client import FFProbeClient
            >>> from fuzzbin.common.config import FFProbeConfig
            >>> 
            >>> ffprobe_config = FFProbeConfig(timeout=60)
            >>> ffprobe_client = FFProbeClient.from_config(ffprobe_config)
            >>> 
            >>> repo = await VideoRepository.from_config(db_config)
            >>> repo.set_ffprobe_client(ffprobe_client)
        """
        self._ffprobe_client = client
        logger.debug(
            "ffprobe_client_set",
            enabled=client is not None,
        )

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
            raise ValueError(
                "FFProbe client not set. Call set_ffprobe_client() first."
            )

        # Import here to avoid circular dependency
        from ..parsers.ffprobe_parser import FFProbeParser

        # Get video record
        video = await self.get_video_by_id(video_id)

        # Determine file path
        if file_path is None:
            file_path_str = video.get("video_file_path")
            if not file_path_str:
                raise ValueError(
                    f"Video {video_id} has no file path and none was provided"
                )
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
            resolution=f"{metadata.get('width')}x{metadata.get('height')}"
            if metadata.get("width")
            else None,
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
        if not self.workspace_root or not absolute_path:
            return None

        try:
            abs_path = Path(absolute_path)
            return str(abs_path.relative_to(self.workspace_root))
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
