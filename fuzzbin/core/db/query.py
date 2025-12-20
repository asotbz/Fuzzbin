"""Fluent query builder for video searches."""

from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


class VideoQuery:
    """Fluent query builder for searching videos."""

    def __init__(self, connection):
        """
        Initialize query builder.

        Args:
            connection: aiosqlite Connection instance
        """
        self._connection = connection
        self._where_clauses: List[str] = []
        self._params: List[Any] = []
        self._include_deleted = False
        self._order_by_clause: Optional[str] = None
        self._limit_value: Optional[int] = None
        self._offset_value: Optional[int] = None
        self._fts_query: Optional[str] = None

    def where_artist(self, artist: str) -> "VideoQuery":
        """Filter by artist name (case-insensitive LIKE)."""
        self._where_clauses.append("LOWER(v.artist) LIKE LOWER(?)")
        self._params.append(f"%{artist}%")
        return self

    def where_title(self, title: str) -> "VideoQuery":
        """Filter by video title (case-insensitive LIKE)."""
        self._where_clauses.append("LOWER(v.title) LIKE LOWER(?)")
        self._params.append(f"%{title}%")
        return self

    def where_album(self, album: str) -> "VideoQuery":
        """Filter by album name (case-insensitive LIKE)."""
        self._where_clauses.append("LOWER(v.album) LIKE LOWER(?)")
        self._params.append(f"%{album}%")
        return self

    def where_genre(self, genre: str) -> "VideoQuery":
        """Filter by genre (case-insensitive LIKE)."""
        self._where_clauses.append("LOWER(v.genre) LIKE LOWER(?)")
        self._params.append(f"%{genre}%")
        return self

    def where_director(self, director: str) -> "VideoQuery":
        """Filter by director name (case-insensitive LIKE)."""
        self._where_clauses.append("LOWER(v.director) LIKE LOWER(?)")
        self._params.append(f"%{director}%")
        return self

    def where_year(self, year: int) -> "VideoQuery":
        """Filter by exact year."""
        self._where_clauses.append("v.year = ?")
        self._params.append(year)
        return self

    def where_year_range(self, start_year: int, end_year: int) -> "VideoQuery":
        """Filter by year range (inclusive)."""
        self._where_clauses.append("v.year BETWEEN ? AND ?")
        self._params.extend([start_year, end_year])
        return self

    def where_imvdb_id(self, imvdb_id: str) -> "VideoQuery":
        """Filter by IMVDb video ID."""
        self._where_clauses.append("v.imvdb_video_id = ?")
        self._params.append(imvdb_id)
        return self

    def where_youtube_id(self, youtube_id: str) -> "VideoQuery":
        """Filter by YouTube video ID."""
        self._where_clauses.append("v.youtube_id = ?")
        self._params.append(youtube_id)
        return self

    def where_vimeo_id(self, vimeo_id: str) -> "VideoQuery":
        """Filter by Vimeo video ID."""
        self._where_clauses.append("v.vimeo_id = ?")
        self._params.append(vimeo_id)
        return self

    def where_file_path(self, path: str) -> "VideoQuery":
        """Filter by video file path (exact match)."""
        self._where_clauses.append("v.video_file_path = ?")
        self._params.append(path)
        return self

    def where_status(self, status: str) -> "VideoQuery":
        """Filter by video status."""
        self._where_clauses.append("v.status = ?")
        self._params.append(status)
        return self

    def where_download_source(self, source: str) -> "VideoQuery":
        """Filter by download source (youtube, vimeo, etc.)."""
        self._where_clauses.append("v.download_source = ?")
        self._params.append(source)
        return self

    def where_duration_range(
        self, min_seconds: Optional[float] = None, max_seconds: Optional[float] = None
    ) -> "VideoQuery":
        """
        Filter by video duration range.

        Args:
            min_seconds: Minimum duration in seconds (inclusive)
            max_seconds: Maximum duration in seconds (inclusive)

        Example:
            .where_duration_range(60, 300)  # Between 1 and 5 minutes
            .where_duration_range(min_seconds=180)  # At least 3 minutes
        """
        if min_seconds is not None:
            self._where_clauses.append("v.duration >= ?")
            self._params.append(min_seconds)
        if max_seconds is not None:
            self._where_clauses.append("v.duration <= ?")
            self._params.append(max_seconds)
        return self

    def where_min_resolution(self, min_width: int, min_height: int) -> "VideoQuery":
        """
        Filter by minimum resolution.

        Args:
            min_width: Minimum width in pixels
            min_height: Minimum height in pixels

        Example:
            .where_min_resolution(1920, 1080)  # At least 1080p
            .where_min_resolution(1280, 720)   # At least 720p
        """
        self._where_clauses.append("v.width >= ? AND v.height >= ?")
        self._params.extend([min_width, min_height])
        return self

    def where_codec(
        self,
        video_codec: Optional[str] = None,
        audio_codec: Optional[str] = None,
    ) -> "VideoQuery":
        """
        Filter by video and/or audio codec.

        Args:
            video_codec: Video codec name (e.g., 'h264', 'hevc', 'vp9')
            audio_codec: Audio codec name (e.g., 'aac', 'mp3', 'opus')

        Example:
            .where_codec(video_codec='h264')
            .where_codec(video_codec='hevc', audio_codec='aac')
        """
        if video_codec is not None:
            self._where_clauses.append("v.video_codec = ?")
            self._params.append(video_codec)
        if audio_codec is not None:
            self._where_clauses.append("v.audio_codec = ?")
            self._params.append(audio_codec)
        return self

    def where_collection(self, collection_name: str) -> "VideoQuery":
        """
        Filter by collection name.

        Args:
            collection_name: Collection name (case-insensitive partial match)

        Example:
            .where_collection("Greatest Hits")
        """
        self._where_clauses.append(
            """
            EXISTS (
                SELECT 1 FROM video_collections vc
                JOIN collections c ON vc.collection_id = c.id
                WHERE vc.video_id = v.id 
                AND LOWER(c.name) LIKE LOWER(?)
                AND c.is_deleted = 0
            )
        """
        )
        self._params.append(f"%{collection_name}%")
        return self

    def where_collection_id(self, collection_id: int) -> "VideoQuery":
        """
        Filter by collection ID.

        Args:
            collection_id: Collection ID

        Example:
            .where_collection_id(5)
        """
        self._where_clauses.append(
            """
            EXISTS (
                SELECT 1 FROM video_collections vc
                WHERE vc.video_id = v.id AND vc.collection_id = ?
            )
        """
        )
        self._params.append(collection_id)
        return self

    def where_tag(self, tag_name: str) -> "VideoQuery":
        """
        Filter by tag name.

        Args:
            tag_name: Tag name (case-insensitive partial match)

        Example:
            .where_tag("rock")
        """
        self._where_clauses.append(
            """
            EXISTS (
                SELECT 1 FROM video_tags vt
                JOIN tags t ON vt.tag_id = t.id
                WHERE vt.video_id = v.id 
                AND LOWER(t.name) LIKE LOWER(?)
            )
        """
        )
        self._params.append(f"%{tag_name}%")
        return self

    def where_tag_id(self, tag_id: int) -> "VideoQuery":
        """
        Filter by tag ID.

        Args:
            tag_id: Tag ID

        Example:
            .where_tag_id(3)
        """
        self._where_clauses.append(
            """
            EXISTS (
                SELECT 1 FROM video_tags vt
                WHERE vt.video_id = v.id AND vt.tag_id = ?
            )
        """
        )
        self._params.append(tag_id)
        return self

    def where_any_tags(self, tag_names: List[str]) -> "VideoQuery":
        """
        Filter by videos having ANY of the specified tags (OR condition).

        Args:
            tag_names: List of tag names (case-insensitive)

        Example:
            .where_any_tags(["rock", "pop"])  # Videos with rock OR pop
        """
        if not tag_names:
            return self

        placeholders = ",".join("?" * len(tag_names))
        self._where_clauses.append(
            f"""
            EXISTS (
                SELECT 1 FROM video_tags vt
                JOIN tags t ON vt.tag_id = t.id
                WHERE vt.video_id = v.id 
                AND LOWER(t.name) IN ({placeholders})
            )
        """
        )
        self._params.extend([name.lower() for name in tag_names])
        return self

    def where_all_tags(self, tag_names: List[str]) -> "VideoQuery":
        """
        Filter by videos having ALL of the specified tags (AND condition).

        Args:
            tag_names: List of tag names (case-insensitive)

        Example:
            .where_all_tags(["rock", "90s"])  # Videos with both rock AND 90s
        """
        if not tag_names:
            return self

        # Add separate EXISTS clause for each tag to ensure ALL are present
        for tag_name in tag_names:
            self._where_clauses.append(
                """
                EXISTS (
                    SELECT 1 FROM video_tags vt
                    JOIN tags t ON vt.tag_id = t.id
                    WHERE vt.video_id = v.id 
                    AND LOWER(t.name) = LOWER(?)
                )
            """
            )
            self._params.append(tag_name)
        return self

    def search(self, query: str) -> "VideoQuery":
        """
        Full-text search using FTS5.

        Args:
            query: FTS5 search query (supports AND, OR, NOT, phrase queries)

        Example:
            .search("rock AND director:smith")
            .search('"official video"')
        """
        self._fts_query = query
        return self

    def include_deleted(self, include: bool = True) -> "VideoQuery":
        """Include soft-deleted records in results."""
        self._include_deleted = include
        return self

    def order_by(self, field: str, desc: bool = False) -> "VideoQuery":
        """
        Order results by field.

        Args:
            field: Field name (title, artist, album, year, created_at, updated_at)
            desc: Sort descending if True
        """
        direction = "DESC" if desc else "ASC"
        valid_fields = {
            "title",
            "artist",
            "album",
            "year",
            "director",
            "genre",
            "created_at",
            "updated_at",
        }

        if field not in valid_fields:
            logger.warning("invalid_order_by_field", field=field)
            return self

        self._order_by_clause = f"v.{field} {direction}"
        return self

    def order_by_collection_position(self, collection_id: int) -> "VideoQuery":
        """
        Order results by position within a collection.

        Args:
            collection_id: Collection ID

        Note:
            This should be used with where_collection_id() filter.
            Videos not in the collection will be excluded.

        Example:
            .where_collection_id(5).order_by_collection_position(5)
        """
        # This requires a JOIN with video_collections table
        # The _build_query method will need to handle this specially
        # For now, we'll store it and handle in query building
        self._order_by_clause = f"""
            (SELECT vc.position FROM video_collections vc 
             WHERE vc.video_id = v.id AND vc.collection_id = {collection_id}),
            v.title
        """
        return self

    def limit(self, count: int) -> "VideoQuery":
        """Limit number of results."""
        self._limit_value = count
        return self

    def offset(self, count: int) -> "VideoQuery":
        """Skip first N results."""
        self._offset_value = count
        return self

    async def execute(self) -> List[Dict[str, Any]]:
        """
        Execute query and return results.

        Returns:
            List of video records as dictionaries
        """
        query, params = self._build_query()

        logger.debug(
            "query_executing",
            query=query,
            params=params,
            fts_query=self._fts_query,
        )

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()

        results = [dict(row) for row in rows]

        logger.info(
            "query_executed",
            results_count=len(results),
            fts_query=self._fts_query,
        )

        return results

    async def count(self) -> int:
        """
        Execute query and return count of matching records.

        Returns:
            Number of matching records
        """
        # Build query without LIMIT/OFFSET
        saved_limit = self._limit_value
        saved_offset = self._offset_value
        self._limit_value = None
        self._offset_value = None

        query, params = self._build_query(count_only=True)

        self._limit_value = saved_limit
        self._offset_value = saved_offset

        cursor = await self._connection.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else 0

    def _build_query(self, count_only: bool = False) -> Tuple[str, List[Any]]:
        """Build SQL query from builder state."""
        if count_only:
            select_clause = "SELECT COUNT(*)"
        else:
            select_clause = "SELECT v.*"

        # Use FTS5 if search query provided
        if self._fts_query:
            from_clause = """
                FROM videos v
                JOIN videos_fts fts ON v.id = fts.rowid
            """
            # Add FTS MATCH clause
            fts_where = "fts.videos_fts MATCH ?"
            self._where_clauses.insert(0, fts_where)
            self._params.insert(0, self._fts_query)
        else:
            from_clause = "FROM videos v"

        # Build WHERE clause
        where_parts = list(self._where_clauses)

        # Add soft delete filter unless explicitly included
        if not self._include_deleted:
            where_parts.append("v.is_deleted = 0")

        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)

        # Build full query
        query_parts = [select_clause, from_clause, where_clause]

        # Add ORDER BY (not for count queries)
        if not count_only and self._order_by_clause:
            query_parts.append(f"ORDER BY {self._order_by_clause}")

        # Add LIMIT/OFFSET (not for count queries)
        if not count_only:
            if self._limit_value is not None:
                query_parts.append(f"LIMIT {self._limit_value}")
            if self._offset_value is not None:
                query_parts.append(f"OFFSET {self._offset_value}")

        query = " ".join(query_parts)
        return query, self._params
