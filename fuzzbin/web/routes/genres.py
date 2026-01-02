"""Genre classification and lookup endpoints."""

from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from fuzzbin.common.genre_buckets import PRIORITY, classify_single_genre

router = APIRouter(prefix="/genres", tags=["Genres"])


class GenreNormalizeResponse(BaseModel):
    """Response for genre classification."""

    original: str = Field(..., description="Original genre value as provided")
    normalized: str = Field(..., description="Classified genre bucket")
    is_mapped: bool = Field(
        ...,
        description="True if genre was mapped to a bucket, False if passed through unchanged",
    )


class GenreCategoriesResponse(BaseModel):
    """Response for available genre categories."""

    categories: List[str] = Field(..., description="List of genre buckets")


@router.get(
    "/normalize",
    response_model=GenreNormalizeResponse,
    summary="Classify genre",
    description=(
        "Classify a genre string to a bucket category. "
        "Genres like 'grunge', 'alternative rock', 'punk rock' map to 'Rock'. "
        "If no mapping exists, the original genre is passed through unchanged."
    ),
)
async def normalize_genre_endpoint(
    genre: str = Query(..., description="Genre string to classify"),
) -> GenreNormalizeResponse:
    """Classify a genre to a bucket category.

    Examples:
        - "grunge" -> {"original": "grunge", "normalized": "Rock", "is_mapped": true}
        - "hip hop" -> {"original": "hip hop", "normalized": "Hip Hop/R&B", "is_mapped": true}
        - "synthwave" -> {"original": "synthwave", "normalized": "Electronic", "is_mapped": true}
    """
    bucket, matched_pattern = classify_single_genre(genre)
    is_mapped = bucket is not None
    return GenreNormalizeResponse(
        original=genre,
        normalized=bucket if bucket else genre,
        is_mapped=is_mapped,
    )


@router.get(
    "/categories",
    response_model=GenreCategoriesResponse,
    summary="List genre buckets",
    description="Get the list of genre buckets used for classification.",
)
async def list_genre_categories() -> GenreCategoriesResponse:
    """List all genre buckets.

    Returns the canonical list of genre buckets:
    Metal, Hip Hop/R&B, Country, Pop, Electronic, Rock
    """
    return GenreCategoriesResponse(categories=list(PRIORITY))


@router.post(
    "/normalize/batch",
    response_model=List[GenreNormalizeResponse],
    summary="Classify multiple genres",
    description="Classify multiple genre strings to buckets in a single request.",
)
async def normalize_genres_batch(
    genres: List[str] = Query(..., description="List of genre strings to classify"),
) -> List[GenreNormalizeResponse]:
    """Classify multiple genres in a single request.

    Useful for processing multiple tracks at once during bulk import.
    """
    results = []
    for genre in genres:
        bucket, matched_pattern = classify_single_genre(genre)
        is_mapped = bucket is not None
        results.append(
            GenreNormalizeResponse(
                original=genre,
                normalized=bucket if bucket else genre,
                is_mapped=is_mapped,
            )
        )
    return results
