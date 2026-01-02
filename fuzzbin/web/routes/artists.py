"""Artist CRUD and management endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from fuzzbin.core.db import VideoRepository

from ..dependencies import get_repository
from ..schemas.artist import ArtistCreate, ArtistResponse, ArtistUpdate
from ..schemas.common import PageParams, PaginatedResponse
from ..schemas.video import VideoResponse

router = APIRouter(prefix="/artists", tags=["Artists"])


@router.get(
    "",
    response_model=PaginatedResponse[ArtistResponse],
    summary="List artists",
    description="Get a paginated list of artists.",
)
async def list_artists(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    name: Optional[str] = Query(default=None, description="Filter by name (partial match)"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted"),
    repo: VideoRepository = Depends(get_repository),
) -> PaginatedResponse[ArtistResponse]:
    """List all artists with pagination."""
    page_params = PageParams(page=page, page_size=page_size)

    # Get all artists (repository doesn't have pagination for artists yet)
    artists = await repo.list_artists(include_deleted=include_deleted)

    # Filter by name if provided
    if name:
        name_lower = name.lower()
        artists = [a for a in artists if name_lower in a["name"].lower()]

    # Calculate pagination
    total = len(artists)
    start = page_params.offset
    end = start + page_params.page_size
    paginated_artists = artists[start:end]

    items = [ArtistResponse.from_db_row(a) for a in paginated_artists]
    return PaginatedResponse.create(items, total, page_params)


@router.get(
    "/{artist_id}",
    response_model=ArtistResponse,
    summary="Get artist by ID",
    description="Get detailed information about a specific artist.",
)
async def get_artist(
    artist_id: int,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    repo: VideoRepository = Depends(get_repository),
) -> ArtistResponse:
    """Get an artist by ID."""
    row = await repo.get_artist_by_id(artist_id, include_deleted=include_deleted)
    return ArtistResponse.from_db_row(row)


@router.post(
    "",
    response_model=ArtistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update artist",
    description="Create a new artist or update if name already exists (upsert).",
)
async def create_artist(
    artist: ArtistCreate,
    repo: VideoRepository = Depends(get_repository),
) -> ArtistResponse:
    """Create or update an artist (upsert by name)."""
    artist_id = await repo.upsert_artist(**artist.to_repo_kwargs())
    row = await repo.get_artist_by_id(artist_id)
    return ArtistResponse.from_db_row(row)


@router.patch(
    "/{artist_id}",
    response_model=ArtistResponse,
    summary="Update artist",
    description="Update artist information. Only provided fields are updated.",
)
async def update_artist(
    artist_id: int,
    artist: ArtistUpdate,
    repo: VideoRepository = Depends(get_repository),
) -> ArtistResponse:
    """Update an artist's information."""
    # Verify artist exists
    await repo.get_artist_by_id(artist_id)

    # Update with provided fields
    updates = artist.to_repo_kwargs()
    if updates:
        await repo.update_artist(artist_id, **updates)

    row = await repo.get_artist_by_id(artist_id)
    return ArtistResponse.from_db_row(row)


@router.delete(
    "/{artist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete artist",
    description="Soft delete an artist.",
)
async def delete_artist(
    artist_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Soft delete an artist."""
    # Verify artist exists
    await repo.get_artist_by_id(artist_id)
    await repo.soft_delete_artist(artist_id)


@router.get(
    "/{artist_id}/videos",
    response_model=PaginatedResponse[VideoResponse],
    summary="Get artist's videos",
    description="Get videos associated with an artist.",
)
async def get_artist_videos(
    artist_id: int,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    role: Optional[str] = Query(default=None, description="Filter by role (primary/featured)"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted"),
    repo: VideoRepository = Depends(get_repository),
) -> PaginatedResponse[VideoResponse]:
    """Get videos for an artist with pagination."""
    # Verify artist exists
    await repo.get_artist_by_id(artist_id)

    page_params = PageParams(page=page, page_size=page_size)

    # Get videos for this artist
    videos = await repo.get_artist_videos(artist_id)

    # Filter by role if provided
    if role:
        videos = [v for v in videos if v.get("role") == role]

    # Calculate pagination
    total = len(videos)
    start = page_params.offset
    end = start + page_params.page_size
    paginated_videos = videos[start:end]

    # Get full video details for each
    items = []
    for v in paginated_videos:
        row = await repo.get_video_by_id(v["id"], include_deleted=include_deleted)
        artists = await repo.get_video_artists(v["id"])
        collections = await repo.get_video_collections(v["id"])
        tags = await repo.get_video_tags(v["id"])
        items.append(
            VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)
        )

    return PaginatedResponse.create(items, total, page_params)


@router.post(
    "/{artist_id}/videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Link artist to video",
    description="Link an artist to a video with specified role.",
)
async def link_artist_to_video(
    artist_id: int,
    video_id: int,
    role: str = Query(default="primary", description="Artist role: primary or featured"),
    position: int = Query(default=0, ge=0, description="Position in credits"),
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Link an artist to a video."""
    # Verify both exist
    await repo.get_artist_by_id(artist_id)
    await repo.get_video_by_id(video_id)

    await repo.link_video_artist(video_id, artist_id, role=role, position=position)


@router.delete(
    "/{artist_id}/videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unlink artist from video",
    description="Remove the link between an artist and a video.",
)
async def unlink_artist_from_video(
    artist_id: int,
    video_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Unlink an artist from a video."""
    # Verify both exist
    await repo.get_artist_by_id(artist_id)
    await repo.get_video_by_id(video_id)

    await repo.unlink_video_artist(video_id, artist_id)
