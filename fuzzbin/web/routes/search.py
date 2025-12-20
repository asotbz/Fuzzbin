"""Full-text search endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from fuzzbin.core.db import VideoRepository

from ..dependencies import get_repository
from ..schemas.common import PageParams, PaginatedResponse
from ..schemas.video import VideoResponse

router = APIRouter(prefix="/search", tags=["Search"])


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
    response_model=dict,
    summary="Get search suggestions",
    description="Get autocomplete suggestions based on partial query.",
)
async def search_suggestions(
    q: str = Query(..., min_length=2, description="Partial search query"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum suggestions"),
    repo: VideoRepository = Depends(get_repository),
) -> dict:
    """
    Get search suggestions for autocomplete.

    Returns suggestions from:
    - Video titles
    - Artist names
    - Album names

    Note: This is a simple implementation. For production, consider
    using a dedicated search index like Elasticsearch or MeiliSearch.
    """
    suggestions = {
        "titles": [],
        "artists": [],
        "albums": [],
    }

    q_lower = q.lower()

    # Search videos for title matches
    query = repo.query().where_title(q).limit(limit)
    videos = await query.execute()
    suggestions["titles"] = list(set(v["title"] for v in videos if v.get("title")))[:limit]

    # Search for artist matches
    artists = await repo.list_artists()
    suggestions["artists"] = [a["name"] for a in artists if q_lower in a["name"].lower()][:limit]

    # Search for album matches (from videos)
    query = repo.query().where_album(q).limit(limit * 2)
    videos = await query.execute()
    suggestions["albums"] = list(set(v["album"] for v in videos if v.get("album")))[:limit]

    return suggestions
