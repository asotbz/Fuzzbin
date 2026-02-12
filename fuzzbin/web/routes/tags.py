"""Tag CRUD and management endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

import fuzzbin
from fuzzbin.core.db import VideoRepository
from fuzzbin.services import TagService

from ..dependencies import get_repository, get_tag_service
from ..schemas.common import (
    AUTH_ERROR_RESPONSES,
    COMMON_ERROR_RESPONSES,
    PageParams,
    PaginatedResponse,
)
from ..schemas.tag import TagCreate, TagResponse, TagsSet
from ..schemas.video import VideoResponse

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get(
    "",
    response_model=PaginatedResponse[TagResponse],
    summary="List tags",
    description="Get a paginated list of tags.",
)
async def list_tags(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    name: Optional[str] = Query(default=None, description="Filter by name (partial match)"),
    min_usage_count: int = Query(default=0, ge=0, description="Minimum usage count"),
    order_by: str = Query(default="name", description="Sort by: name or usage_count"),
    repo: VideoRepository = Depends(get_repository),
) -> PaginatedResponse[TagResponse]:
    """List all tags with pagination."""
    page_params = PageParams(page=page, page_size=page_size)

    # Get all tags
    tags = await repo.list_tags(min_usage_count=min_usage_count, order_by=order_by)

    # Filter by name if provided
    if name:
        name_lower = name.lower()
        tags = [t for t in tags if name_lower in t["name"].lower()]

    # Calculate pagination
    total = len(tags)
    start = page_params.offset
    end = start + page_params.page_size
    paginated_tags = tags[start:end]

    items = [TagResponse.from_db_row(t) for t in paginated_tags]
    return PaginatedResponse.create(items, total, page_params)


@router.get(
    "/{tag_id}",
    response_model=TagResponse,
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Get tag by ID",
    description="Get detailed information about a specific tag.",
)
async def get_tag(
    tag_id: int,
    repo: VideoRepository = Depends(get_repository),
) -> TagResponse:
    """Get a tag by ID."""
    row = await repo.get_tag_by_id(tag_id)
    return TagResponse.from_db_row(row)


@router.post(
    "",
    response_model=TagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tag",
    description="Create a new tag (name will be normalized to lowercase if tags.normalize is enabled).",
)
async def create_tag(
    tag: TagCreate,
    repo: VideoRepository = Depends(get_repository),
) -> TagResponse:
    """Create a new tag."""
    config = fuzzbin.get_config()
    tag_id = await repo.upsert_tag(tag.name, normalize=config.tags.normalize)
    row = await repo.get_tag_by_id(tag_id)
    return TagResponse.from_db_row(row)


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **AUTH_ERROR_RESPONSES,
        400: COMMON_ERROR_RESPONSES[400],
        404: COMMON_ERROR_RESPONSES[404],
    },
    summary="Delete tag",
    description="Delete a tag. Tags with usage_count > 0 cannot be deleted directly.",
)
async def delete_tag(
    tag_id: int,
    force: bool = Query(default=False, description="Force delete even if in use"),
    repo: VideoRepository = Depends(get_repository),
) -> None:
    """Delete a tag."""
    tag = await repo.get_tag_by_id(tag_id)

    if tag["usage_count"] > 0 and not force:
        raise HTTPException(
            status_code=400,
            detail=f"Tag is in use by {tag['usage_count']} videos. Use force=true to delete anyway.",
        )

    await repo.delete_tag(tag_id)


@router.get(
    "/{tag_id}/videos",
    response_model=PaginatedResponse[VideoResponse],
    responses={**AUTH_ERROR_RESPONSES, 404: COMMON_ERROR_RESPONSES[404]},
    summary="Get videos with tag",
    description="Get videos that have a specific tag.",
)
async def get_tag_videos(
    tag_id: int,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    include_deleted: bool = Query(default=False, description="Include soft-deleted videos"),
    repo: VideoRepository = Depends(get_repository),
) -> PaginatedResponse[VideoResponse]:
    """Get videos with a specific tag."""
    # Verify tag exists
    await repo.get_tag_by_id(tag_id)

    page_params = PageParams(page=page, page_size=page_size)

    # Get videos with this tag
    videos = await repo.get_videos_by_tag(tag_id)

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
            if include_deleted:
                raise
            continue

    return PaginatedResponse.create(items, total, page_params)


# Video tag management endpoints (nested under /videos but included here for organization)


@router.post(
    "/videos/{video_id}/set",
    response_model=List[TagResponse],
    summary="Set video tags",
    description="Replace all tags on a video with the provided list.",
)
async def set_video_tags(
    video_id: int,
    tags_set: TagsSet,
    repo: VideoRepository = Depends(get_repository),
    tag_service: TagService = Depends(get_tag_service),
) -> List[TagResponse]:
    """Set (replace) all tags on a video."""
    # Verify video exists
    await repo.get_video_by_id(video_id)

    # Set tags via service (handles NFO sync)
    video_tags = await tag_service.set_video_tags(
        video_id,
        tags_set.tags,
        source=tags_set.source,
        replace_existing=True,
    )

    # Return updated tags
    return [
        TagResponse(
            id=t["id"],
            name=t["name"],
            normalized_name=t.get("normalized_name", t["name"].lower()),
            created_at=t.get("created_at"),
            usage_count=t.get("usage_count", 0),
        )
        for t in video_tags
    ]


@router.post(
    "/videos/{video_id}/add",
    response_model=List[TagResponse],
    summary="Add tags to video",
    description="Add tags to a video without removing existing ones.",
)
async def add_video_tags(
    video_id: int,
    tags_set: TagsSet,
    repo: VideoRepository = Depends(get_repository),
    tag_service: TagService = Depends(get_tag_service),
) -> List[TagResponse]:
    """Add tags to a video (keeps existing)."""
    # Verify video exists
    await repo.get_video_by_id(video_id)

    # Add tags via service (handles NFO sync)
    video_tags = await tag_service.set_video_tags(
        video_id,
        tags_set.tags,
        source=tags_set.source,
        replace_existing=False,
    )

    # Return updated tags
    return [
        TagResponse(
            id=t["id"],
            name=t["name"],
            normalized_name=t.get("normalized_name", t["name"].lower()),
            created_at=t.get("created_at"),
            usage_count=t.get("usage_count", 0),
        )
        for t in video_tags
    ]


@router.delete(
    "/videos/{video_id}/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove tag from video",
    description="Remove a specific tag from a video.",
)
async def remove_video_tag(
    video_id: int,
    tag_id: int,
    repo: VideoRepository = Depends(get_repository),
    tag_service: TagService = Depends(get_tag_service),
) -> None:
    """Remove a tag from a video."""
    # Verify both exist
    await repo.get_video_by_id(video_id)
    await repo.get_tag_by_id(tag_id)

    await tag_service.remove_video_tag(video_id, tag_id)
