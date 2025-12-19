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
