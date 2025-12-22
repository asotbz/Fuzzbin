"""Common schema types for pagination, sorting, and filtering."""

from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Number of items per page")

    @property
    def offset(self) -> int:
        """Calculate offset for database query."""
        return (self.page - 1) * self.page_size


class SortParams(BaseModel):
    """Sorting parameters for list endpoints."""

    sort_by: str = Field(
        default="created_at",
        description="Field to sort by",
    )
    sort_order: Literal["asc", "desc"] = Field(
        default="desc",
        description="Sort order (asc or desc)",
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.

    Example:
        {
            "items": [...],
            "total": 100,
            "page": 1,
            "page_size": 20,
            "total_pages": 5
        }
    """

    items: List[T]
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")

    @classmethod
    def create(cls, items: List[T], total: int, page_params: PageParams) -> "PaginatedResponse[T]":
        """
        Create a paginated response from items and pagination params.

        Args:
            items: List of items for current page
            total: Total count of all items
            page_params: Pagination parameters used

        Returns:
            PaginatedResponse instance
        """
        total_pages = (total + page_params.page_size - 1) // page_params.page_size
        return cls(
            items=items,
            total=total,
            page=page_params.page,
            page_size=page_params.page_size,
            total_pages=max(1, total_pages),
        )


class ErrorDetail(BaseModel):
    """Standard error response detail."""

    detail: str = Field(description="Error message")
    error_type: str = Field(description="Error type identifier")


class ValidationErrorDetail(BaseModel):
    """Validation error detail with field locations."""

    loc: List[str] = Field(description="Error location path")
    msg: str = Field(description="Error message")
    type: str = Field(description="Error type")


class ValidationErrorResponse(BaseModel):
    """Validation error response with multiple field errors."""

    detail: str = Field(default="Validation error")
    error_type: str = Field(default="validation_error")
    errors: List[ValidationErrorDetail] = Field(description="List of validation errors")


# ==================== Common Error Responses ====================

# Reusable responses dict for OpenAPI documentation.
# Import and spread into route decorators: responses={**COMMON_ERROR_RESPONSES, ...}
COMMON_ERROR_RESPONSES = {
    400: {
        "model": ErrorDetail,
        "description": "Bad Request - Invalid input or business rule violation",
    },
    401: {
        "model": ErrorDetail,
        "description": "Unauthorized - Authentication required or token invalid",
    },
    403: {
        "model": ErrorDetail,
        "description": "Forbidden - Insufficient permissions or account disabled",
    },
    404: {
        "model": ErrorDetail,
        "description": "Not Found - Resource does not exist",
    },
    409: {
        "model": ErrorDetail,
        "description": "Conflict - Resource already exists or state conflict",
    },
    500: {
        "model": ErrorDetail,
        "description": "Internal Server Error - Unexpected server error",
    },
}

# Subset for routes that don't require authentication
PUBLIC_ERROR_RESPONSES = {
    400: COMMON_ERROR_RESPONSES[400],
    404: COMMON_ERROR_RESPONSES[404],
    500: COMMON_ERROR_RESPONSES[500],
}

# Subset for authenticated routes (includes auth errors)
AUTH_ERROR_RESPONSES = {
    401: COMMON_ERROR_RESPONSES[401],
    403: COMMON_ERROR_RESPONSES[403],
}


# ==================== Concrete Response Models ====================


class HealthCheckResponse(BaseModel):
    """Health check endpoint response."""

    status: str = Field(description="Health status ('ok' or 'error')")
    version: str = Field(description="API version string")
    auth_enabled: bool = Field(description="Whether authentication is enabled")


class SearchSuggestionItem(BaseModel):
    """Single search suggestion category."""

    titles: List[str] = Field(default_factory=list, description="Matching video titles")
    artists: List[str] = Field(default_factory=list, description="Matching artist names")
    albums: List[str] = Field(default_factory=list, description="Matching album names")


class SearchSuggestionsResponse(BaseModel):
    """Search suggestions response for autocomplete."""

    titles: List[str] = Field(default_factory=list, description="Matching video titles")
    artists: List[str] = Field(default_factory=list, description="Matching artist names")
    albums: List[str] = Field(default_factory=list, description="Matching album names")


class VideoStatusHistoryEntry(BaseModel):
    """Single entry in video status history."""

    id: int = Field(description="History entry ID")
    video_id: int = Field(description="Video ID")
    old_status: Optional[str] = Field(description="Previous status value")
    new_status: str = Field(description="New status value")
    reason: Optional[str] = Field(default=None, description="Reason for status change")
    changed_at: str = Field(description="ISO timestamp of status change")


class VideoStatusHistoryResponse(BaseModel):
    """Video status history response."""

    items: List[VideoStatusHistoryEntry] = Field(description="Status history entries")
