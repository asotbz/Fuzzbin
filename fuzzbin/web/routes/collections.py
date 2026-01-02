"""Collection CRUD and management endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from fuzzbin.core.db import VideoRepository

from ..dependencies import get_repository
from ..schemas.collection import (
    CollectionCreate,
    CollectionResponse,
    CollectionUpdate,
)
from ..schemas.common import PageParams, PaginatedResponse
from ..schemas.video import VideoResponse

router = APIRouter(prefix="/collections", tags=["Collections"])


@router.get(
    "",
    response_model=PaginatedResponse[CollectionResponse],
    summary="List collections",
    description="Get a paginated list of collections.",
)
async def list_collections(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    name: Optional[str] = Query(default=None, description="Filter by name (partial match)"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted"),
    repo: VideoRepository = Depends(get_repository),
) -> PaginatedResponse[CollectionResponse]:
    """List all collections with pagination."""
    page_params = PageParams(page=page, page_size=page_size)

    # Get all collections
    collections = await repo.list_collections(include_deleted=include_deleted)

    # Filter by name if provided
    if name:
        name_lower = name.lower()
        collections = [c for c in collections if name_lower in c["name"].lower()]

    # Calculate pagination
    total = len(collections)
    start = page_params.offset
    end = start + page_params.page_size
    paginated_collections = collections[start:end]

    # Get video counts
    items = []
    for c in paginated_collections:
        videos = await repo.get_collection_videos(c["id"])
        items.append(CollectionResponse.from_db_row(c, video_count=len(videos)))

    return PaginatedResponse.create(items, total, page_params)


@router.get(
    "/{collection_id}",
    response_model=CollectionResponse,
    summary="Get collection by ID",
    description="Get detailed information about a specific collection.",
)
async def get_collection(
    collection_id: int,
    include_deleted: bool = Query(default=False, description="Include if soft-deleted"),
    repo: VideoRepository = Depends(get_repository),
) -> CollectionResponse:
    """Get a collection by ID."""
    row = await repo.get_collection_by_id(collection_id, include_deleted=include_deleted)
    videos = await repo.get_collection_videos(collection_id)
    return CollectionResponse.from_db_row(row, video_count=len(videos))


@router.post(
    "",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create collection",
    description="Create a new collection.",
)
async def create_collection(
    collection: CollectionCreate,
    repo: VideoRepository = Depends(get_repository),
) -> CollectionResponse:
    """Create a new collection."""
    collection_id = await repo.upsert_collection(**collection.to_repo_kwargs())
    row = await repo.get_collection_by_id(collection_id)
    return CollectionResponse.from_db_row(row, video_count=0)


@router.patch(
    "/{collection_id}",
    response_model=CollectionResponse,
    summary="Update collection",
    description="Update collection information. Only provided fields are updated.",
)
async def update_collection(
    collection_id: int,
    collection: CollectionUpdate,
    repo: VideoRepository = Depends(get_repository),
) -> CollectionResponse:
    """Update a collection's information."""
    # Verify collection exists
    await repo.get_collection_by_id(collection_id)

    # Update with provided fields
    updates = collection.to_repo_kwargs()
    if updates:
        await repo.update_collection(collection_id, **updates)

    row = await repo.get_collection_by_id(collection_id)
    videos = await repo.get_collection_videos(collection_id)
    return CollectionResponse.from_db_row(row, video_count=len(videos))


@router.delete(
    "/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete collection",
    description="Soft delete a collection.",
)
async def delete_collection(
    collection_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Soft delete a collection."""
    # Verify collection exists
    await repo.get_collection_by_id(collection_id)
    await repo.soft_delete_collection(collection_id)


@router.get(
    "/{collection_id}/videos",
    response_model=PaginatedResponse[VideoResponse],
    summary="Get collection videos",
    description="Get videos in a collection, ordered by position.",
)
async def get_collection_videos(
    collection_id: int,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted videos"),
    repo: VideoRepository = Depends(get_repository),
) -> PaginatedResponse[VideoResponse]:
    """Get videos in a collection with pagination."""
    # Verify collection exists
    await repo.get_collection_by_id(collection_id)

    page_params = PageParams(page=page, page_size=page_size)

    # Get videos in collection (ordered by position)
    videos = await repo.get_collection_videos(collection_id)

    # Calculate pagination
    total = len(videos)
    start = page_params.offset
    end = start + page_params.page_size
    paginated_videos = videos[start:end]

    # Get full video details for each
    items = []
    for v in paginated_videos:
        try:
            row = await repo.get_video_by_id(v["id"], include_deleted=include_deleted)
            artists = await repo.get_video_artists(v["id"])
            collections = await repo.get_video_collections(v["id"])
            tags = await repo.get_video_tags(v["id"])
            items.append(
                VideoResponse.from_db_row(row, artists=artists, collections=collections, tags=tags)
            )
        except Exception:
            # Skip videos that can't be found (may be deleted)
            if include_deleted:
                raise
            continue

    return PaginatedResponse.create(items, total, page_params)


@router.post(
    "/{collection_id}/videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Add video to collection",
    description="Add a video to a collection with optional position.",
)
async def add_video_to_collection(
    collection_id: int,
    video_id: int,
    position: Optional[int] = Query(default=None, ge=0, description="Position in collection"),
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Add a video to a collection."""
    # Verify both exist
    await repo.get_collection_by_id(collection_id)
    await repo.get_video_by_id(video_id)

    await repo.add_video_to_collection(video_id, collection_id, position=position)


@router.delete(
    "/{collection_id}/videos/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove video from collection",
    description="Remove a video from a collection.",
)
async def remove_video_from_collection(
    collection_id: int,
    video_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Remove a video from a collection."""
    # Verify both exist
    await repo.get_collection_by_id(collection_id)
    await repo.get_video_by_id(video_id)

    await repo.remove_video_from_collection(video_id, collection_id)
