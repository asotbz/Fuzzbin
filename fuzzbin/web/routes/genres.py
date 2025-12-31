"""Genre normalization and lookup endpoints."""

from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from fuzzbin.common.string_utils import (
    get_primary_genre_categories,
    normalize_genre,
)

router = APIRouter(prefix="/genres", tags=["Genres"])


class GenreNormalizeResponse(BaseModel):
    """Response for genre normalization."""

    original: str = Field(..., description="Original genre value as provided")
    normalized: str = Field(..., description="Normalized primary genre category")
    is_mapped: bool = Field(
        ...,
        description="True if genre was mapped to a primary category, False if passed through unchanged",
    )


class GenreCategoriesResponse(BaseModel):
    """Response for available genre categories."""

    categories: List[str] = Field(..., description="List of primary genre categories")


@router.get(
    "/normalize",
    response_model=GenreNormalizeResponse,
    summary="Normalize genre",
    description=(
        "Normalize a genre string to a primary category. "
        "Genres like 'grunge', 'alternative rock', 'punk rock' map to 'Rock'. "
        "If no mapping exists, the original genre is passed through unchanged."
    ),
)
async def normalize_genre_endpoint(
    genre: str = Query(..., description="Genre string to normalize"),
) -> GenreNormalizeResponse:
    """Normalize a genre to a primary category.

    Examples:
        - "grunge" -> {"original": "grunge", "normalized": "Rock", "is_mapped": true}
        - "hip hop" -> {"original": "hip hop", "normalized": "Hip Hop/R&B", "is_mapped": true}
        - "synthwave" -> {"original": "synthwave", "normalized": "synthwave", "is_mapped": false}
    """
    original, normalized, is_mapped = normalize_genre(genre)
    return GenreNormalizeResponse(
        original=original,
        normalized=normalized,
        is_mapped=is_mapped,
    )


@router.get(
    "/categories",
    response_model=GenreCategoriesResponse,
    summary="List genre categories",
    description="Get the list of primary genre categories used for normalization.",
)
async def list_genre_categories() -> GenreCategoriesResponse:
    """List all primary genre categories.

    Returns the canonical list of primary genre categories:
    Rock, Pop, Hip Hop/R&B, Country, Electronic, Jazz, Classical, Metal, Folk, Other
    """
    return GenreCategoriesResponse(categories=get_primary_genre_categories())


@router.post(
    "/normalize/batch",
    response_model=List[GenreNormalizeResponse],
    summary="Normalize multiple genres",
    description="Normalize multiple genre strings to primary categories in a single request.",
)
async def normalize_genres_batch(
    genres: List[str] = Query(..., description="List of genre strings to normalize"),
) -> List[GenreNormalizeResponse]:
    """Normalize multiple genres in a single request.

    Useful for processing multiple tracks at once during bulk import.
    """
    results = []
    for genre in genres:
        original, normalized, is_mapped = normalize_genre(genre)
        results.append(
            GenreNormalizeResponse(
                original=original,
                normalized=normalized,
                is_mapped=is_mapped,
            )
        )
    return results
