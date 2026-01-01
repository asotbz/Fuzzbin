"""Full-text search endpoint."""

import json
from typing import Annotated, Dict, List, Optional

import structlog
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

import fuzzbin
from fuzzbin.auth.schemas import UserInfo
from fuzzbin.core.db import VideoRepository

from ..dependencies import get_current_user, get_repository, require_auth
from ..schemas.common import (
    PageParams,
    PaginatedResponse,
    SearchSuggestionsResponse,
    AUTH_ERROR_RESPONSES,
)
from ..schemas.video import VideoResponse

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])

# In-memory facet cache with TTL
# Default: 60 seconds (can be overridden via advanced config)
_facet_cache: TTLCache = None

# Default facet cache TTL in seconds
DEFAULT_FACET_CACHE_TTL = 60


def _get_facet_cache() -> TTLCache:
    """Get or create facet cache with configured TTL."""
    global _facet_cache
    if _facet_cache is None:
        _facet_cache = TTLCache(maxsize=10, ttl=DEFAULT_FACET_CACHE_TTL)
    return _facet_cache


def clear_facet_cache() -> None:
    """Clear the facet cache. Useful for testing."""
    global _facet_cache
    if _facet_cache is not None:
        _facet_cache.clear()


# ==================== Facet Schemas ====================


class FacetItem(BaseModel):
    """Single facet value with count."""

    value: str = Field(description="Facet value (e.g., tag name, genre)")
    count: int = Field(description="Number of videos with this value")


class FacetsResponse(BaseModel):
    """Response containing all facets for filtering UI."""

    tags: List[FacetItem] = Field(default_factory=list, description="Tag facets with counts")
    genres: List[FacetItem] = Field(default_factory=list, description="Genre facets with counts")
    years: List[FacetItem] = Field(default_factory=list, description="Year facets with counts")
    directors: List[FacetItem] = Field(
        default_factory=list, description="Director facets with counts"
    )
    total_videos: int = Field(default=0, description="Total number of videos in the library")

    @classmethod
    def from_repo_facets(
        cls, facets: Dict[str, List[dict]], total_videos: int = 0
    ) -> "FacetsResponse":
        """Create from repository facets dict."""
        return cls(
            tags=[FacetItem(**f) for f in facets.get("tags", [])],
            genres=[FacetItem(**f) for f in facets.get("genres", [])],
            years=[FacetItem(**f) for f in facets.get("years", [])],
            directors=[FacetItem(**f) for f in facets.get("directors", [])],
            total_videos=total_videos,
        )


# ==================== Saved Search Schemas ====================


class SavedSearchCreate(BaseModel):
    """Request to create a saved search."""

    name: str = Field(..., min_length=1, max_length=100, description="Name for the saved search")
    description: Optional[str] = Field(
        default=None, max_length=500, description="Optional description"
    )
    query: dict = Field(
        ...,
        description="Search/filter parameters to save",
        examples=[{"search": "nirvana", "genre": "Rock", "year_min": 1990}],
    )


class SavedSearchResponse(BaseModel):
    """Response for a saved search."""

    id: int = Field(description="Saved search ID")
    name: str = Field(description="Saved search name")
    description: Optional[str] = Field(description="Optional description")
    query: dict = Field(description="Saved search/filter parameters")
    created_at: str = Field(description="Creation timestamp")
    updated_at: str = Field(description="Last update timestamp")

    @classmethod
    def from_db_row(cls, row: dict) -> "SavedSearchResponse":
        """Create from database row."""
        return cls(
            id=row["id"],
            name=row["name"],
            description=row.get("description"),
            query=json.loads(row["query_json"]) if row.get("query_json") else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


class SavedSearchListResponse(BaseModel):
    """Response for listing saved searches."""

    items: List[SavedSearchResponse] = Field(description="List of saved searches")
    total: int = Field(description="Total count")


# ==================== Search Endpoints ====================


@router.get(
    "",
    response_model=PaginatedResponse[VideoResponse],
    summary="Search videos",
    description="Full-text search across video metadata using FTS5. "
    "Supports AND, OR, NOT operators and phrase matching with quotes.",
)
async def search_videos(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted videos"),
    repo: VideoRepository = Depends(get_repository),
) -> PaginatedResponse[VideoResponse]:
    """
    Full-text search across videos.

    The search uses SQLite FTS5 and supports:
    - Simple keywords: `nirvana teen spirit`
    - Phrases: `"smells like teen spirit"`
    - AND: `nirvana AND unplugged`
    - OR: `nirvana OR pearl jam`
    - NOT: `nirvana NOT unplugged`
    - Prefix matching: `nirv*`

    Search is performed across title, artist, album, director, genre, and studio fields.
    """
    page_params = PageParams(page=page, page_size=page_size)

    # Build search query
    query = repo.query()

    if include_deleted:
        query = query.include_deleted()

    # Apply FTS5 search
    query = query.search(q)

    # Get total count
    total = await query.count()

    # Apply pagination
    query = query.limit(page_params.page_size).offset(page_params.offset)

    # Execute search
    rows = await query.execute()

    # Build responses with relationships
    items = []
    for row in rows:
        video_id = row["id"]
        artists = await repo.get_video_artists(video_id)
        collections = await repo.get_video_collections(video_id)
        tags = await repo.get_video_tags(video_id)
        items.append(
            VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)
        )

    return PaginatedResponse.create(items, total, page_params)


@router.get(
    "/suggestions",
    response_model=SearchSuggestionsResponse,
    responses={**AUTH_ERROR_RESPONSES},
    summary="Get search suggestions",
    description="Get autocomplete suggestions based on partial query.",
)
async def search_suggestions(
    q: str = Query(..., min_length=2, description="Partial search query"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum suggestions"),
    repo: VideoRepository = Depends(get_repository),
) -> SearchSuggestionsResponse:
    """
    Get search suggestions for autocomplete.

    Returns suggestions from:
    - Video titles
    - Artist names
    - Album names

    Note: This is a simple implementation. For production, consider
    using a dedicated search index like Elasticsearch or MeiliSearch.
    """
    q_lower = q.lower()

    # Search videos for title matches
    query = repo.query().where_title(q).limit(limit)
    videos = await query.execute()
    titles = list(set(v["title"] for v in videos if v.get("title")))[:limit]

    # Search for artist matches
    artists_list = await repo.list_artists()
    artists = [a["name"] for a in artists_list if q_lower in a["name"].lower()][:limit]

    # Search for album matches (from videos)
    query = repo.query().where_album(q).limit(limit * 2)
    videos = await query.execute()
    albums = list(set(v["album"] for v in videos if v.get("album")))[:limit]

    return SearchSuggestionsResponse(
        titles=titles,
        artists=artists,
        albums=albums,
    )


# ==================== Facet Endpoints ====================


@router.get(
    "/facets",
    response_model=FacetsResponse,
    summary="Get search facets",
    description="Get faceted counts for building filter UIs. Results are cached briefly.",
)
async def get_facets(
    include_deleted: bool = Query(default=False, description="Include soft-deleted videos"),
    repo: VideoRepository = Depends(get_repository),
) -> FacetsResponse:
    """
    Get faceted counts for filtering.

    Returns counts by:
    - Tags (most used first)
    - Genres (most used first)
    - Years (newest first)
    - Directors (most videos first)

    Results are cached for the configured TTL (default 60s) to improve performance.
    """
    cache = _get_facet_cache()
    cache_key = f"facets:{include_deleted}"

    # Check cache
    if cache_key in cache:
        logger.debug("facets_cache_hit", cache_key=cache_key)
        return cache[cache_key]

    # Fetch from database
    facets = await repo.get_facets(include_deleted=include_deleted)

    # Get total video count
    total_videos = await repo.query().count()

    response = FacetsResponse.from_repo_facets(facets, total_videos=total_videos)

    # Cache result
    cache[cache_key] = response
    logger.debug(
        "facets_cached",
        cache_key=cache_key,
        tags=len(response.tags),
        genres=len(response.genres),
        years=len(response.years),
        directors=len(response.directors),
    )

    return response


# ==================== Saved Search Endpoints ====================


@router.post(
    "/saved",
    response_model=SavedSearchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create saved search",
    description="Save a search query for later reuse.",
)
async def create_saved_search(
    request: SavedSearchCreate,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> SavedSearchResponse:
    """Create a new saved search."""
    query_json = json.dumps(request.query, ensure_ascii=False)

    search_id = await repo.create_saved_search(
        name=request.name,
        query_json=query_json,
        description=request.description,
    )

    # Fetch created search
    row = await repo.get_saved_search_by_id(search_id)

    logger.info(
        "saved_search_created",
        search_id=search_id,
        name=request.name,
        user=current_user.username if current_user else "anonymous",
    )

    return SavedSearchResponse.from_db_row(row)


@router.get(
    "/saved",
    response_model=SavedSearchListResponse,
    summary="List saved searches",
    description="Get all saved searches.",
)
async def list_saved_searches(
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
    repo: VideoRepository = Depends(get_repository),
) -> SavedSearchListResponse:
    """List all saved searches."""
    rows = await repo.get_saved_searches()

    return SavedSearchListResponse(
        items=[SavedSearchResponse.from_db_row(row) for row in rows],
        total=len(rows),
    )


@router.get(
    "/saved/{search_id}",
    response_model=SavedSearchResponse,
    summary="Get saved search",
    description="Get a saved search by ID.",
)
async def get_saved_search(
    search_id: int,
    current_user: Annotated[Optional[UserInfo], Depends(get_current_user)],
    repo: VideoRepository = Depends(get_repository),
) -> SavedSearchResponse:
    """Get a saved search by ID."""
    try:
        row = await repo.get_saved_search_by_id(search_id)
        return SavedSearchResponse.from_db_row(row)
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Saved search not found: {search_id}",
            )
        raise


@router.delete(
    "/saved/{search_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete saved search",
    description="Delete a saved search.",
)
async def delete_saved_search(
    search_id: int,
    current_user: Annotated[UserInfo, Depends(require_auth)],
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Delete a saved search."""
    try:
        await repo.delete_saved_search(search_id)
        logger.info(
            "saved_search_deleted",
            search_id=search_id,
            user=current_user.username if current_user else "anonymous",
        )
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Saved search not found: {search_id}",
            )
        raise
