"""IMVDb API routes for music video database access.

Provides endpoints for searching and retrieving music video metadata
from the Internet Music Video Database (IMVDb).
"""

import structlog
from fastapi import APIRouter, Depends, Query

from fuzzbin.api.imvdb_client import IMVDbClient

from ..dependencies import get_imvdb_client
from ..schemas.imvdb import (
    IMVDbEntityDetail,
    IMVDbEntitySearchResponse,
    IMVDbEntityVideosPageResponse,
    IMVDbVideoDetail,
    IMVDbVideoSearchResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/imvdb", tags=["IMVDb"])


@router.get(
    "/search/videos",
    response_model=IMVDbVideoSearchResponse,
    summary="Search for music videos",
    response_description="Paginated list of matching music videos",
)
async def search_videos(
    artist: str = Query(..., description="Artist name to search for"),
    track: str = Query(..., description="Track/song title to search for"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(25, ge=1, le=100, description="Results per page"),
    client: IMVDbClient = Depends(get_imvdb_client),
) -> IMVDbVideoSearchResponse:
    """
    Search IMVDb for music videos by artist and track title.

    Returns paginated results with video thumbnails, release year, and artist info.
    Use `/imvdb/videos/{video_id}` to get full details including credits and sources.

    **Rate Limited:** Shares rate limit with other IMVDb endpoints.

    **Cached:** Results are cached for 30 minutes.
    """
    logger.info("imvdb_search_videos", artist=artist, track=track, page=page)

    result = await client.search_videos(
        artist=artist,
        track_title=track,
        page=page,
        per_page=per_page,
    )

    return IMVDbVideoSearchResponse(
        total_results=result.pagination.total_results,
        current_page=result.pagination.current_page,
        per_page=result.pagination.per_page,
        total_pages=result.pagination.total_pages,
        results=[
            {
                "id": v.id,
                "production_status": v.production_status,
                "song_title": v.song_title,
                "song_slug": v.song_slug,
                "url": v.url,
                "multiple_versions": v.multiple_versions,
                "version_name": v.version_name,
                "version_number": v.version_number,
                "is_imvdb_pick": v.is_imvdb_pick,
                "aspect_ratio": v.aspect_ratio,
                "year": v.year,
                "verified_credits": v.verified_credits,
                "artists": [
                    {"name": a.name, "slug": a.slug, "url": a.url} for a in (v.artists or [])
                ],
                "image": v.image,
            }
            for v in result.results
        ],
    )


@router.get(
    "/search/entities",
    response_model=IMVDbEntitySearchResponse,
    summary="Search for artists/directors/entities",
    response_description="Paginated list of matching entities",
)
async def search_entities(
    q: str = Query(..., description="Search query (artist name, director, etc.)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(25, ge=1, le=100, description="Results per page"),
    client: IMVDbClient = Depends(get_imvdb_client),
) -> IMVDbEntitySearchResponse:
    """
    Search IMVDb for entities (artists, directors, production companies, etc.).

    Returns paginated results with entity IDs, Discogs links, and video counts.
    Use `/imvdb/entities/{entity_id}` to get full details including video listings.

    **Rate Limited:** Shares rate limit with other IMVDb endpoints.

    **Cached:** Results are cached for 30 minutes.
    """
    logger.info("imvdb_search_entities", query=q, page=page)

    result = await client.search_entities(
        query=q,
        page=page,
        per_page=per_page,
    )

    return IMVDbEntitySearchResponse(
        total_results=result.pagination.total_results,
        current_page=result.pagination.current_page,
        per_page=result.pagination.per_page,
        total_pages=result.pagination.total_pages,
        results=[
            {
                "id": e.id,
                "name": e.name,
                "slug": e.slug,
                "url": e.url,
                "discogs_id": e.discogs_id,
                "byline": e.byline,
                "bio": e.bio,
                "image": e.image,
                "artist_video_count": e.artist_video_count,
                "featured_video_count": e.featured_video_count,
            }
            for e in result.results
        ],
    )


@router.get(
    "/videos/{video_id}",
    response_model=IMVDbVideoDetail,
    summary="Get video details",
    response_description="Full video metadata including credits and sources",
)
async def get_video(
    video_id: int,
    client: IMVDbClient = Depends(get_imvdb_client),
) -> IMVDbVideoDetail:
    """
    Get detailed metadata for an IMVDb video.

    Returns full video information including:
    - Primary and featured artists
    - Directors and full crew credits
    - Video sources (YouTube, Vimeo, etc.)
    - Multiple version information
    - Production status and release year

    **Rate Limited:** Shares rate limit with other IMVDb endpoints.

    **Cached:** Results are cached for 30 minutes.
    """
    logger.info("imvdb_get_video", video_id=video_id)

    video = await client.get_video(video_id)

    # Convert the parsed model to our response schema
    return IMVDbVideoDetail(
        id=video.id,
        production_status=video.production_status,
        song_title=video.song_title,
        song_slug=video.song_slug,
        url=video.url,
        multiple_versions=video.multiple_versions,
        version_name=video.version_name,
        version_number=video.version_number,
        is_imvdb_pick=video.is_imvdb_pick,
        aspect_ratio=video.aspect_ratio,
        year=video.year,
        verified_credits=video.verified_credits,
        artists=[{"name": a.name, "slug": a.slug, "url": a.url} for a in (video.artists or [])],
        featured_artists=[
            {"name": a.name, "slug": a.slug, "url": a.url} for a in (video.featured_artists or [])
        ],
        image=video.image,
        sources=[
            {
                "source": s.source,
                "source_slug": s.source_slug,
                "source_data": s.source_data,
                "is_primary": s.is_primary,
            }
            for s in (video.sources or [])
        ],
        directors=[
            {
                "position_name": d.position_name,
                "position_code": d.position_code,
                "entity_name": d.entity_name,
                "entity_slug": d.entity_slug,
                "entity_id": d.entity_id,
                "entity_url": d.entity_url,
                "position_notes": d.position_notes,
                "position_id": d.position_id,
            }
            for d in (video.directors or [])
        ],
        credits=video.credits,
    )


@router.get(
    "/entities/{entity_id}",
    response_model=IMVDbEntityDetail,
    summary="Get entity details",
    response_description="Full entity metadata including video listings",
)
async def get_entity(
    entity_id: int,
    client: IMVDbClient = Depends(get_imvdb_client),
) -> IMVDbEntityDetail:
    """
    Get detailed metadata for an IMVDb entity (artist, director, etc.).

    Returns full entity information including:
    - Profile information and biography
    - Discogs ID for cross-referencing
    - Videos as primary artist
    - Videos as featured artist

    **Rate Limited:** Shares rate limit with other IMVDb endpoints.

    **Cached:** Results are cached for 30 minutes.
    """
    logger.info("imvdb_get_entity", entity_id=entity_id)

    entity = await client.get_entity(entity_id)

    # Convert the parsed model to our response schema
    artist_videos = None
    if entity.artist_videos:
        artist_videos = {
            "total_videos": entity.artist_videos.total_videos,
            "videos": [
                {
                    "id": v.id,
                    "production_status": v.production_status,
                    "song_title": v.song_title,
                    "song_slug": v.song_slug,
                    "url": v.url,
                    "multiple_versions": v.multiple_versions,
                    "version_name": v.version_name,
                    "version_number": v.version_number,
                    "is_imvdb_pick": v.is_imvdb_pick,
                    "aspect_ratio": v.aspect_ratio,
                    "year": v.year,
                    "verified_credits": v.verified_credits,
                    "artists": [
                        {"name": a.name, "slug": a.slug, "url": a.url} for a in (v.artists or [])
                    ],
                    "image": v.image,
                }
                for v in entity.artist_videos.videos
            ],
        }

    featured_videos = None
    if entity.featured_videos:
        featured_videos = {
            "total_videos": entity.featured_videos.total_videos,
            "videos": [
                {
                    "id": v.id,
                    "production_status": v.production_status,
                    "song_title": v.song_title,
                    "song_slug": v.song_slug,
                    "url": v.url,
                    "multiple_versions": v.multiple_versions,
                    "version_name": v.version_name,
                    "version_number": v.version_number,
                    "is_imvdb_pick": v.is_imvdb_pick,
                    "aspect_ratio": v.aspect_ratio,
                    "year": v.year,
                    "verified_credits": v.verified_credits,
                    "artists": [
                        {"name": a.name, "slug": a.slug, "url": a.url} for a in (v.artists or [])
                    ],
                    "image": v.image,
                }
                for v in entity.featured_videos.videos
            ],
        }

    return IMVDbEntityDetail(
        id=entity.id,
        name=entity.name,
        slug=entity.slug,
        url=entity.url,
        discogs_id=entity.discogs_id,
        byline=entity.byline,
        bio=entity.bio,
        image=entity.image,
        artist_video_count=entity.artist_video_count,
        featured_video_count=entity.featured_video_count,
        artist_videos=artist_videos,
        featured_videos=featured_videos,
    )


@router.get(
    "/entities/{entity_id}/videos",
    response_model=IMVDbEntityVideosPageResponse,
    summary="Get paginated artist videos",
    response_description="Paginated list of videos for the artist",
)
async def get_entity_videos(
    entity_id: int,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(50, ge=1, le=100, description="Results per page"),
    client: IMVDbClient = Depends(get_imvdb_client),
) -> IMVDbEntityVideosPageResponse:
    """
    Get paginated artist videos for an IMVDb entity.

    Supports lazy loading for the artist import workflow. Returns videos
    in the order they appear on IMVDb (typically by release year descending).

    Use `has_more` to determine if additional pages are available.

    **Rate Limited:** Shares rate limit with other IMVDb endpoints.

    **Cached:** Results are cached for 30 minutes.
    """
    logger.info("imvdb_get_entity_videos", entity_id=entity_id, page=page, per_page=per_page)

    result = await client.get_entity_videos(entity_id, page=page, per_page=per_page)

    return IMVDbEntityVideosPageResponse(
        entity_id=result.entity_id,
        entity_slug=result.entity_slug,
        entity_name=result.entity_name,
        total_videos=result.total_videos,
        current_page=result.current_page,
        per_page=result.per_page,
        total_pages=result.total_pages,
        has_more=result.has_more,
        videos=[
            {
                "id": v.id,
                "production_status": v.production_status,
                "song_title": v.song_title,
                "song_slug": v.song_slug,
                "url": v.url,
                "multiple_versions": v.multiple_versions,
                "version_name": v.version_name,
                "version_number": v.version_number,
                "is_imvdb_pick": v.is_imvdb_pick,
                "aspect_ratio": v.aspect_ratio,
                "year": v.year,
                "verified_credits": v.verified_credits,
                "artists": [
                    {"name": a.name, "slug": a.slug, "url": a.url} for a in (v.artists or [])
                ],
                "image": v.image,
            }
            for v in result.videos
        ],
    )
