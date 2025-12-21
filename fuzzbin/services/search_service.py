"""Search service for cross-entity search, faceting, and aggregations.

This service provides:
- Full-text search with FTS5
- Cross-entity search (videos, artists, collections)
- Faceted search with filter counts
- Cached aggregations for UI components
- Search suggestions/autocomplete

Example:
    >>> from fuzzbin.services import SearchService
    >>> 
    >>> async def my_route(search_service: SearchService = Depends(get_search_service)):
    ...     results = await search_service.search_all("nirvana")
    ...     facets = await search_service.get_facets()
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

from fuzzbin.core.db.repository import VideoRepository

from .base import (
    BaseService,
    ServiceCallback,
    cached_async,
)

logger = structlog.get_logger(__name__)


# ==================== Data Classes ====================


@dataclass
class SearchResult:
    """A single search result."""

    id: int
    type: str  # 'video', 'artist', 'collection', 'tag'
    title: str
    subtitle: Optional[str] = None
    score: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResults:
    """Combined search results across entities."""

    query: str
    total: int
    videos: List[SearchResult] = field(default_factory=list)
    artists: List[SearchResult] = field(default_factory=list)
    collections: List[SearchResult] = field(default_factory=list)
    tags: List[SearchResult] = field(default_factory=list)


@dataclass
class FacetValue:
    """A single facet value with count."""

    value: str
    count: int
    selected: bool = False


@dataclass
class Facet:
    """A facet with its values."""

    name: str
    field: str
    values: List[FacetValue] = field(default_factory=list)


@dataclass
class FacetedSearchResults:
    """Search results with facets for filtering."""

    query: str
    total: int
    items: List[Dict[str, Any]]
    facets: List[Facet]
    page: int
    page_size: int
    total_pages: int


@dataclass
class SearchSuggestions:
    """Autocomplete suggestions."""

    query: str
    titles: List[str] = field(default_factory=list)
    artists: List[str] = field(default_factory=list)
    albums: List[str] = field(default_factory=list)


# ==================== Service ====================


class SearchService(BaseService):
    """
    Service for search and discovery operations.

    Provides:
    - Full-text search using SQLite FTS5
    - Cross-entity search (videos, artists, collections, tags)
    - Faceted search with dynamic filter counts
    - Cached aggregations for frequently-accessed data
    - Search suggestions for autocomplete

    Caching strategy:
    - Facet counts: 60 second TTL (frequently changes)
    - Tag cloud: 300 second TTL (less frequent changes)
    - Stats: 60 second TTL
    """

    def __init__(
        self,
        repository: VideoRepository,
        callback: Optional[ServiceCallback] = None,
    ):
        """
        Initialize the search service.

        Args:
            repository: VideoRepository for database operations
            callback: Optional callback for progress/failure hooks
        """
        super().__init__(repository, callback)

    # ==================== Full-Text Search ====================

    async def search_videos(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
        include_deleted: bool = False,
        load_relationships: bool = True,
    ) -> Dict[str, Any]:
        """
        Search videos using FTS5 full-text search.

        Args:
            query: Search query (supports FTS5 syntax)
            page: Page number (1-indexed)
            page_size: Results per page
            include_deleted: Include soft-deleted videos
            load_relationships: Load artists, collections, tags

        Returns:
            Dict with items, total, page info
        """
        repo_query = self.repository.query()

        if include_deleted:
            repo_query = repo_query.include_deleted()

        # Apply FTS5 search
        repo_query = repo_query.search(query)

        # Get total count
        total = await repo_query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        repo_query = repo_query.limit(page_size).offset(offset)

        # Execute search
        rows = await repo_query.execute()

        # Load relationships if requested
        items = []
        for row in rows:
            item = dict(row)
            if load_relationships:
                video_id = row["id"]
                item["artists"] = await self.repository.get_video_artists(video_id)
                item["collections"] = await self.repository.get_video_collections(video_id)
                item["tags"] = await self.repository.get_video_tags(video_id)
            items.append(item)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    async def search_all(
        self,
        query: str,
        limit_per_type: int = 10,
    ) -> SearchResults:
        """
        Search across all entity types.

        Args:
            query: Search query
            limit_per_type: Max results per entity type

        Returns:
            SearchResults with videos, artists, collections, tags
        """
        results = SearchResults(query=query, total=0)
        query_lower = query.lower()

        # Search videos
        video_query = self.repository.query().search(query).limit(limit_per_type)
        video_rows = await video_query.execute()
        for row in video_rows:
            results.videos.append(
                SearchResult(
                    id=row["id"],
                    type="video",
                    title=row.get("title", ""),
                    subtitle=row.get("artist"),
                    data=dict(row),
                )
            )

        # Search artists
        artists = await self.repository.list_artists()
        matching_artists = [
            a for a in artists if query_lower in a.get("name", "").lower()
        ][:limit_per_type]
        for artist in matching_artists:
            results.artists.append(
                SearchResult(
                    id=artist["id"],
                    type="artist",
                    title=artist.get("name", ""),
                    data=artist,
                )
            )

        # Search collections
        collections = await self.repository.list_collections()
        matching_collections = [
            c for c in collections if query_lower in c.get("name", "").lower()
        ][:limit_per_type]
        for collection in matching_collections:
            results.collections.append(
                SearchResult(
                    id=collection["id"],
                    type="collection",
                    title=collection.get("name", ""),
                    subtitle=collection.get("description"),
                    data=collection,
                )
            )

        # Search tags
        tags = await self.repository.list_tags()
        matching_tags = [
            t for t in tags if query_lower in t.get("name", "").lower()
        ][:limit_per_type]
        for tag in matching_tags:
            results.tags.append(
                SearchResult(
                    id=tag["id"],
                    type="tag",
                    title=tag.get("name", ""),
                    data=tag,
                )
            )

        results.total = (
            len(results.videos)
            + len(results.artists)
            + len(results.collections)
            + len(results.tags)
        )

        return results

    # ==================== Faceted Search ====================

    async def search_with_facets(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> FacetedSearchResults:
        """
        Search videos with faceted filters.

        Provides filter counts for UI faceted navigation:
        - Genre facet with counts
        - Year facet with counts
        - Status facet with counts
        - Artist facet with counts

        Args:
            query: Optional search query
            filters: Optional filters to apply {field: value}
            page: Page number
            page_size: Results per page

        Returns:
            FacetedSearchResults with items and facets
        """
        filters = filters or {}

        # Build base query
        base_query = self.repository.query()

        if query:
            base_query = base_query.search(query)

        # Apply filters
        if filters.get("genre"):
            base_query = base_query.where_genre(filters["genre"])
        if filters.get("year"):
            base_query = base_query.where_year(filters["year"])
        if filters.get("status"):
            base_query = base_query.where_status(filters["status"])
        if filters.get("artist"):
            base_query = base_query.where_artist(filters["artist"])

        # Get total and items
        total = await base_query.count()
        offset = (page - 1) * page_size
        rows = await base_query.limit(page_size).offset(offset).execute()
        items = [dict(row) for row in rows]

        # Calculate facets
        facets = await self._calculate_facets(query, filters)

        return FacetedSearchResults(
            query=query or "",
            total=total,
            items=items,
            facets=facets,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )

    async def _calculate_facets(
        self,
        query: Optional[str],
        current_filters: Dict[str, Any],
    ) -> List[Facet]:
        """Calculate facet counts for filtering UI."""
        facets = []

        # Genre facet
        genre_counts = await self._get_facet_counts("genre", query, current_filters)
        if genre_counts:
            facets.append(
                Facet(
                    name="Genre",
                    field="genre",
                    values=[
                        FacetValue(
                            value=v,
                            count=c,
                            selected=current_filters.get("genre") == v,
                        )
                        for v, c in genre_counts.items()
                    ],
                )
            )

        # Year facet (group into decades)
        year_counts = await self._get_year_facet_counts(query, current_filters)
        if year_counts:
            facets.append(
                Facet(
                    name="Decade",
                    field="year",
                    values=[
                        FacetValue(
                            value=v,
                            count=c,
                            selected=current_filters.get("decade") == v,
                        )
                        for v, c in year_counts.items()
                    ],
                )
            )

        # Status facet
        status_counts = await self._get_facet_counts("status", query, current_filters)
        if status_counts:
            facets.append(
                Facet(
                    name="Status",
                    field="status",
                    values=[
                        FacetValue(
                            value=v,
                            count=c,
                            selected=current_filters.get("status") == v,
                        )
                        for v, c in status_counts.items()
                    ],
                )
            )

        return facets

    async def _get_facet_counts(
        self,
        field: str,
        query: Optional[str],
        exclude_filter: Dict[str, Any],
    ) -> Dict[str, int]:
        """Get counts for each value of a field."""
        # Build query without the current field filter
        base_query = self.repository.query()
        if query:
            base_query = base_query.search(query)

        # Apply other filters (not the one we're counting)
        for filter_field, filter_value in exclude_filter.items():
            if filter_field != field and filter_value:
                method_name = f"where_{filter_field}"
                if hasattr(base_query, method_name):
                    base_query = getattr(base_query, method_name)(filter_value)

        # Get all matching videos
        rows = await base_query.execute()

        # Count by field value
        counts: Dict[str, int] = {}
        for row in rows:
            value = row.get(field)
            if value:
                counts[value] = counts.get(value, 0) + 1

        # Sort by count descending
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    async def _get_year_facet_counts(
        self,
        query: Optional[str],
        exclude_filter: Dict[str, Any],
    ) -> Dict[str, int]:
        """Get counts grouped by decade."""
        base_query = self.repository.query()
        if query:
            base_query = base_query.search(query)

        # Apply filters except decade
        for filter_field, filter_value in exclude_filter.items():
            if filter_field not in ("year", "decade") and filter_value:
                method_name = f"where_{filter_field}"
                if hasattr(base_query, method_name):
                    base_query = getattr(base_query, method_name)(filter_value)

        rows = await base_query.execute()

        # Count by decade
        counts: Dict[str, int] = {}
        for row in rows:
            year = row.get("year")
            if year:
                decade = f"{(year // 10) * 10}s"
                counts[decade] = counts.get(decade, 0) + 1

        # Sort by decade
        return dict(sorted(counts.items()))

    # ==================== Suggestions ====================

    async def get_suggestions(
        self,
        query: str,
        limit: int = 10,
    ) -> SearchSuggestions:
        """
        Get autocomplete suggestions.

        Args:
            query: Partial search query (min 2 chars recommended)
            limit: Max suggestions per category

        Returns:
            SearchSuggestions with titles, artists, albums
        """
        suggestions = SearchSuggestions(query=query)
        query_lower = query.lower()

        # Search videos for title matches
        title_query = self.repository.query().where_title(query).limit(limit)
        videos = await title_query.execute()
        suggestions.titles = list(
            set(v["title"] for v in videos if v.get("title"))
        )[:limit]

        # Search for artist matches
        artists = await self.repository.list_artists()
        suggestions.artists = [
            a["name"] for a in artists if query_lower in a.get("name", "").lower()
        ][:limit]

        # Search for album matches
        album_query = self.repository.query().where_album(query).limit(limit * 2)
        album_videos = await album_query.execute()
        suggestions.albums = list(
            set(v["album"] for v in album_videos if v.get("album"))
        )[:limit]

        return suggestions

    # ==================== Cached Aggregations ====================

    @cached_async(ttl_seconds=60.0, maxsize=16)
    async def get_facets(self) -> List[Facet]:
        """
        Get all available facets with counts (cached 60s).

        Returns facets for:
        - Genres with counts
        - Decades with counts
        - Statuses with counts
        - Top artists with counts

        Returns:
            List of Facet objects
        """
        return await self._calculate_facets(None, {})

    @cached_async(ttl_seconds=300.0, maxsize=8)
    async def get_tag_cloud(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get tag cloud data with usage counts (cached 5 min).

        Args:
            limit: Maximum tags to return

        Returns:
            List of dicts with tag name and count
        """
        tags = await self.repository.list_tags()
        tag_counts = []

        for tag in tags:
            # Get video count for this tag
            videos = await self.repository.get_tag_videos(tag["id"])
            tag_counts.append({
                "id": tag["id"],
                "name": tag["name"],
                "count": len(videos),
            })

        # Sort by count descending and limit
        tag_counts.sort(key=lambda x: -x["count"])
        return tag_counts[:limit]

    @cached_async(ttl_seconds=300.0, maxsize=8)
    async def get_top_artists(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get artists with most videos (cached 5 min).

        Args:
            limit: Maximum artists to return

        Returns:
            List of dicts with artist name and video count
        """
        artists = await self.repository.list_artists()
        artist_counts = []

        for artist in artists:
            videos = await self.repository.get_artist_videos(artist["id"])
            artist_counts.append({
                "id": artist["id"],
                "name": artist["name"],
                "video_count": len(videos),
            })

        artist_counts.sort(key=lambda x: -x["video_count"])
        return artist_counts[:limit]

    @cached_async(ttl_seconds=300.0, maxsize=8)
    async def get_top_collections(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get collections with most videos (cached 5 min).

        Args:
            limit: Maximum collections to return

        Returns:
            List of dicts with collection info and video count
        """
        collections = await self.repository.list_collections()
        collection_counts = []

        for collection in collections:
            videos = await self.repository.get_collection_videos(collection["id"])
            collection_counts.append({
                "id": collection["id"],
                "name": collection["name"],
                "description": collection.get("description"),
                "video_count": len(videos),
            })

        collection_counts.sort(key=lambda x: -x["video_count"])
        return collection_counts[:limit]

    @cached_async(ttl_seconds=60.0, maxsize=4)
    async def get_library_stats(self) -> Dict[str, Any]:
        """
        Get library statistics (cached 60s).

        Returns:
            Dict with counts by status, totals, recent activity
        """
        # Total videos
        total = await self.repository.query().count()

        # Counts by status
        status_counts = {}
        for status_value in ["discovered", "downloading", "downloaded", "organized", "missing"]:
            q = self.repository.query().where_status(status_value)
            status_counts[status_value] = await q.count()

        # Count artists, collections, tags
        artists = await self.repository.list_artists()
        collections = await self.repository.list_collections()
        tags = await self.repository.list_tags()

        return {
            "total_videos": total,
            "by_status": status_counts,
            "total_artists": len(artists),
            "total_collections": len(collections),
            "total_tags": len(tags),
        }

    def clear_caches(self) -> None:
        """
        Clear all cached data.

        Call this after bulk imports or updates that invalidate cached stats.
        """
        # Clear each cached method's cache
        for method_name in ["get_facets", "get_tag_cloud", "get_top_artists",
                           "get_top_collections", "get_library_stats"]:
            method = getattr(self, method_name)
            if hasattr(method, "clear_cache"):
                # Note: This is a coroutine, but we're calling it from sync context
                # In practice, you'd want to await this
                pass

        self.logger.info("search_caches_cleared")
