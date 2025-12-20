"""Video CRUD and management endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from fuzzbin.core.db import VideoRepository

from ..dependencies import get_repository
from ..schemas.common import PageParams, PaginatedResponse, SortParams
from ..schemas.video import (
    VideoCreate,
    VideoFilters,
    VideoResponse,
    VideoStatusUpdate,
    VideoUpdate,
)

router = APIRouter(prefix="/videos", tags=["Videos"])

# Valid sort fields for videos
VALID_VIDEO_SORT_FIELDS = {
    "title",
    "artist",
    "album",
    "year",
    "director",
    "genre",
    "created_at",
    "updated_at",
    "status",
}


@router.get(
    "",
    response_model=PaginatedResponse[VideoResponse],
    summary="List videos",
    description="Get a paginated list of videos with optional filters and sorting.",
)
async def list_videos(
    # Pagination
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    # Sorting
    sort_by: str = Query(default="created_at", description="Sort field"),
    sort_order: str = Query(default="desc", description="Sort order: asc or desc"),
    # Filters
    title: Optional[str] = Query(default=None, description="Filter by title"),
    artist: Optional[str] = Query(default=None, description="Filter by artist"),
    album: Optional[str] = Query(default=None, description="Filter by album"),
    director: Optional[str] = Query(default=None, description="Filter by director"),
    genre: Optional[str] = Query(default=None, description="Filter by genre"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    year: Optional[int] = Query(default=None, description="Filter by year"),
    year_min: Optional[int] = Query(default=None, description="Minimum year"),
    year_max: Optional[int] = Query(default=None, description="Maximum year"),
    imvdb_video_id: Optional[str] = Query(default=None, description="Filter by IMVDb ID"),
    youtube_id: Optional[str] = Query(default=None, description="Filter by YouTube ID"),
    collection_name: Optional[str] = Query(default=None, description="Filter by collection"),
    collection_id: Optional[int] = Query(default=None, description="Filter by collection ID"),
    tag_name: Optional[str] = Query(default=None, description="Filter by tag"),
    tag_id: Optional[int] = Query(default=None, description="Filter by tag ID"),
    search: Optional[str] = Query(default=None, description="Full-text search"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted"),
    # Dependencies
    repo: VideoRepository = Depends(get_repository),
) -> PaginatedResponse[VideoResponse]:
    """List videos with filtering, sorting, and pagination."""
    page_params = PageParams(page=page, page_size=page_size)
    filters = VideoFilters(
        title=title,
        artist=artist,
        album=album,
        director=director,
        genre=genre,
        status=status,
        year=year,
        year_min=year_min,
        year_max=year_max,
        imvdb_video_id=imvdb_video_id,
        youtube_id=youtube_id,
        collection_name=collection_name,
        collection_id=collection_id,
        tag_name=tag_name,
        tag_id=tag_id,
        search=search,
        include_deleted=include_deleted,
    )

    # Build query
    query = repo.query()
    query = filters.apply_to_query(query)

    # Apply sorting
    if sort_by in VALID_VIDEO_SORT_FIELDS:
        desc = sort_order.lower() == "desc"
        query = query.order_by(sort_by, desc=desc)

    # Get total count before pagination
    total = await query.count()

    # Apply pagination
    query = query.limit(page_params.page_size).offset(page_params.offset)

    # Execute query
    rows = await query.execute()

    # Convert to response models with relationships
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
    "/{video_id}",
    response_model=VideoResponse,
    summary="Get video by ID",
    description="Get detailed information about a specific video.",
)
async def get_video(
    video_id: int,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    repo: VideoRepository = Depends(get_repository),
) -> VideoResponse:
    """Get a video by ID with relationships."""
    row = await repo.get_video_by_id(video_id, include_deleted=include_deleted)
    artists = await repo.get_video_artists(video_id)
    collections = await repo.get_video_collections(video_id)
    tags = await repo.get_video_tags(video_id)
    return VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)


@router.post(
    "",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create video",
    description="Create a new video record.",
)
async def create_video(
    video: VideoCreate,
    repo: VideoRepository = Depends(get_repository),
) -> VideoResponse:
    """Create a new video."""
    video_id = await repo.create_video(**video.to_repo_kwargs())

    # If file paths were provided, update them separately
    if video.video_file_path or video.nfo_file_path:
        await repo.update_video(
            video_id,
            video_file_path=video.video_file_path,
            nfo_file_path=video.nfo_file_path,
        )

    row = await repo.get_video_by_id(video_id)
    return VideoResponse.from_db_row(row)


@router.patch(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Update video",
    description="Update video metadata. Only provided fields are updated.",
)
async def update_video(
    video_id: int,
    video: VideoUpdate,
    repo: VideoRepository = Depends(get_repository),
) -> VideoResponse:
    """Update a video's metadata."""
    # Verify video exists
    await repo.get_video_by_id(video_id)

    # Update with provided fields
    updates = video.to_repo_kwargs()
    if updates:
        await repo.update_video(video_id, **updates)

    # Fetch updated video with relationships
    row = await repo.get_video_by_id(video_id)
    artists = await repo.get_video_artists(video_id)
    collections = await repo.get_video_collections(video_id)
    tags = await repo.get_video_tags(video_id)
    return VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)


@router.patch(
    "/{video_id}/status",
    response_model=VideoResponse,
    summary="Update video status",
    description="Update the status of a video with optional reason and metadata.",
)
async def update_video_status(
    video_id: int,
    status_update: VideoStatusUpdate,
    repo: VideoRepository = Depends(get_repository),
) -> VideoResponse:
    """Update a video's status with tracking."""
    # Verify video exists
    await repo.get_video_by_id(video_id)

    # Update status
    await repo.update_status(
        video_id=video_id,
        new_status=status_update.status,
        reason=status_update.reason,
        changed_by=status_update.changed_by or "api",
        metadata=status_update.metadata,
    )

    # Fetch updated video
    row = await repo.get_video_by_id(video_id)
    artists = await repo.get_video_artists(video_id)
    collections = await repo.get_video_collections(video_id)
    tags = await repo.get_video_tags(video_id)
    return VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)


@router.delete(
    "/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete video",
    description="Soft delete a video (can be restored later).",
)
async def delete_video(
    video_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Soft delete a video."""
    # Verify video exists
    await repo.get_video_by_id(video_id)
    await repo.delete_video(video_id)


@router.post(
    "/{video_id}/restore",
    response_model=VideoResponse,
    summary="Restore video",
    description="Restore a soft-deleted video.",
)
async def restore_video(
    video_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> VideoResponse:
    """Restore a soft-deleted video."""
    # Verify video exists (including deleted)
    await repo.get_video_by_id(video_id, include_deleted=True)
    await repo.restore_video(video_id)

    row = await repo.get_video_by_id(video_id)
    artists = await repo.get_video_artists(video_id)
    collections = await repo.get_video_collections(video_id)
    tags = await repo.get_video_tags(video_id)
    return VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)


@router.delete(
    "/{video_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete video",
    description="Permanently delete a video. This cannot be undone.",
)
async def hard_delete_video(
    video_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Permanently delete a video."""
    # Verify video exists (including deleted)
    await repo.get_video_by_id(video_id, include_deleted=True)
    await repo.hard_delete_video(video_id)


@router.get(
    "/{video_id}/status-history",
    response_model=List[dict],
    summary="Get status history",
    description="Get the status change history for a video.",
)
async def get_video_status_history(
    video_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> List[dict]:
    """Get a video's status change history."""
    # Verify video exists
    await repo.get_video_by_id(video_id, include_deleted=True)
    return await repo.get_status_history(video_id)
