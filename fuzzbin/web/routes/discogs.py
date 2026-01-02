"""Discogs API routes for music release database access.

Provides endpoints for searching and retrieving music release metadata
from Discogs, the largest music database and marketplace.
"""

from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query

from fuzzbin.api.discogs_client import DiscogsClient

from ..dependencies import get_discogs_client
from ..schemas.discogs import (
    DiscogsArtistReleasesResponse,
    DiscogsMaster,
    DiscogsRelease,
    DiscogsSearchResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/discogs", tags=["Discogs"])


@router.get(
    "/search",
    response_model=DiscogsSearchResponse,
    summary="Search for releases",
    response_description="Paginated list of matching releases",
)
async def search_releases(
    artist: Optional[str] = Query(None, description="Artist name to search for"),
    track: Optional[str] = Query(None, description="Track title to search for"),
    q: Optional[str] = Query(None, description="General search query"),
    type: str = Query("master", description="Result type: master, release, artist"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Results per page"),
    client: DiscogsClient = Depends(get_discogs_client),
) -> DiscogsSearchResponse:
    """
    Search Discogs for music releases by artist and/or track title.

    Returns paginated results with release thumbnails, year, format, and label info.
    Use `/discogs/masters/{master_id}` or `/discogs/releases/{release_id}` for full details.

    **Search modes:**
    - Use `artist` + `track` for targeted music video lookups
    - Use `q` for general free-text search
    - Default type is `master` (canonical release), use `release` for specific pressings

    **Rate Limited:** 60 requests/minute (authenticated). Shares rate limit with other Discogs endpoints.

    **Cached:** Results are cached for 2 hours.
    """
    # Build search query
    if artist and track:
        query = f"{artist} {track}"
    elif q:
        query = q
    elif artist:
        query = artist
    else:
        query = track or ""

    logger.info(
        "discogs_search",
        query=query,
        type=type,
        page=page,
    )

    result = await client.search(
        artist=artist or "",
        track=track or "",
        page=page,
        per_page=per_page,
    )

    return DiscogsSearchResponse(
        pagination={
            "page": result.get("pagination", {}).get("page", page),
            "pages": result.get("pagination", {}).get("pages", 1),
            "per_page": result.get("pagination", {}).get("per_page", per_page),
            "items": result.get("pagination", {}).get("items", 0),
            "urls": result.get("pagination", {}).get("urls", {}),
        },
        results=[
            {
                "id": r.get("id"),
                "type": r.get("type", "master"),
                "master_id": r.get("master_id"),
                "master_url": r.get("master_url"),
                "uri": r.get("uri", ""),
                "title": r.get("title", ""),
                "country": r.get("country"),
                "year": r.get("year"),
                "format": r.get("format", []),
                "label": r.get("label", []),
                "genre": r.get("genre", []),
                "style": r.get("style", []),
                "catno": r.get("catno"),
                "barcode": r.get("barcode", []),
                "thumb": r.get("thumb"),
                "cover_image": r.get("cover_image"),
                "resource_url": r.get("resource_url", ""),
                "community": r.get("community"),
            }
            for r in result.get("results", [])
        ],
    )


@router.get(
    "/masters/{master_id}",
    response_model=DiscogsMaster,
    summary="Get master release details",
    response_description="Full master release metadata",
)
async def get_master(
    master_id: int,
    client: DiscogsClient = Depends(get_discogs_client),
) -> DiscogsMaster:
    """
    Get detailed metadata for a Discogs master release.

    A master release represents the canonical version of an album across
    all its various pressings and formats.

    Returns full information including:
    - Complete tracklist with durations
    - Artists with proper credits
    - Genres and styles
    - Cover images at various sizes
    - Related videos (music videos, documentaries)
    - Market statistics (for sale count, lowest price)
    - Links to all release versions

    **Rate Limited:** 60 requests/minute (authenticated).

    **Cached:** Results are cached for 2 hours.
    """
    logger.info("discogs_get_master", master_id=master_id)

    master = await client.get_master(master_id)

    return DiscogsMaster(**master)


@router.get(
    "/releases/{release_id}",
    response_model=DiscogsRelease,
    summary="Get specific release details",
    response_description="Full release metadata",
)
async def get_release(
    release_id: int,
    client: DiscogsClient = Depends(get_discogs_client),
) -> DiscogsRelease:
    """
    Get detailed metadata for a specific Discogs release.

    A release represents a specific pressing/version of an album with
    unique catalog numbers, barcodes, and format details.

    Returns full information including:
    - Complete tracklist with durations
    - Label and catalog information
    - Format details (vinyl, CD, etc.)
    - All identifiers (barcodes, matrix numbers)
    - Extra artists (producers, engineers, etc.)
    - Release notes and credits
    - Cover images
    - Related videos

    **Rate Limited:** 60 requests/minute (authenticated).

    **Cached:** Results are cached for 2 hours.
    """
    logger.info("discogs_get_release", release_id=release_id)

    release = await client.get_release(release_id)

    return DiscogsRelease(**release)


@router.get(
    "/artists/{artist_id}/releases",
    response_model=DiscogsArtistReleasesResponse,
    summary="Get artist discography",
    response_description="Paginated list of artist's releases",
)
async def get_artist_releases(
    artist_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Results per page"),
    sort: str = Query("year", description="Sort field: year, title, format"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    client: DiscogsClient = Depends(get_discogs_client),
) -> DiscogsArtistReleasesResponse:
    """
    Get an artist's complete discography from Discogs.

    Returns a paginated list of all releases associated with an artist,
    including albums, singles, compilations, and appearances.

    Each release includes:
    - Release/Master ID and type
    - Title and year
    - Artist role (Main, Remix, Producer, etc.)
    - Thumbnail image
    - Community statistics (want/have counts)

    **Rate Limited:** 60 requests/minute (authenticated).

    **Cached:** Results are cached for 2 hours.
    """
    logger.info(
        "discogs_get_artist_releases",
        artist_id=artist_id,
        page=page,
        sort=sort,
    )

    result = await client.get_artist_releases(
        artist_id=artist_id,
        page=page,
        per_page=per_page,
    )

    return DiscogsArtistReleasesResponse(
        pagination={
            "page": result.get("pagination", {}).get("page", page),
            "pages": result.get("pagination", {}).get("pages", 1),
            "per_page": result.get("pagination", {}).get("per_page", per_page),
            "items": result.get("pagination", {}).get("items", 0),
            "urls": result.get("pagination", {}).get("urls", {}),
        },
        releases=[
            {
                "id": r.get("id"),
                "type": r.get("type", "release"),
                "main_release": r.get("main_release"),
                "artist": r.get("artist", ""),
                "title": r.get("title", ""),
                "year": r.get("year"),
                "resource_url": r.get("resource_url", ""),
                "role": r.get("role", "Main"),
                "thumb": r.get("thumb"),
                "status": r.get("status"),
                "format": r.get("format"),
                "label": r.get("label"),
                "stats": r.get("stats"),
            }
            for r in result.get("releases", [])
        ],
    )
