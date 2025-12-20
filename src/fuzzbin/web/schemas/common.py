"""Common schema types for pagination, sorting, and filtering."""

from typing import Generic, List, Literal, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        default=20, ge=1, le=100, description="Number of items per page"
    )

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
    def create(
        cls, items: List[T], total: int, page_params: PageParams
    ) -> "PaginatedResponse[T]":
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
