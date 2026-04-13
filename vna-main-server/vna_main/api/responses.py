"""Standard response models for consistent API responses."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Generic, TypeVar, Optional, List
from datetime import datetime, timezone

T = TypeVar('T')

class BaseResponse(BaseModel):
    """Base response model with common fields."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-04-05T12:00:00Z",
                "path": "/api/v1/resources"
            }
        }
    )
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    path: Optional[str] = None

class PaginatedResponse(BaseResponse, Generic[T]):
    """Standard paginated response format."""
    items: List[T]
    total: int
    offset: int = 0
    limit: int = 100
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 0,
                "offset": 0,
                "limit": 100,
                "timestamp": "2026-04-05T12:00:00Z",
                "path": "/api/v1/resources"
            }
        }
    )

class SuccessResponse(BaseResponse):
    """Standard success response."""
    success: bool = True
    message: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "timestamp": "2026-04-05T12:00:00Z"
            }
        }
    )

class ErrorResponse(BaseResponse):
    """Standard error response."""
    success: bool = False
    error: str
    details: Optional[dict] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": "Validation failed",
                "details": {"field": "email", "issue": "Invalid format"},
                "timestamp": "2026-04-05T12:00:00Z"
            }
        }
    )

class ResourceCreatedResponse(SuccessResponse):
    """Response for resource creation."""
    resource_id: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "resource_id": "res_1234567890abcdef",
                "timestamp": "2026-04-05T12:00:00Z"
            }
        }
    )