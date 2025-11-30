"""
Memory Machines Backend - Standardized Response Models

Provides consistent response structure across all endpoints.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: str = Field(..., description="Error code for programmatic handling")
    message: str = Field(..., description="Human-readable error message")

    model_config = {
        "json_schema_extra": {
            "example": {"code": "VALIDATION_ERROR", "message": "missing tenant_id or log_id"}
        }
    }


class APIResponse(BaseModel):
    """Standardized API response structure."""

    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[Any] = Field(None, description="Response data on success")
    error: Optional[ErrorDetail] = Field(None, description="Error details on failure")

    model_config = {
        "json_schema_extra": {
            "example": {"success": True, "data": {"status": "processed"}, "error": None}
        }
    }


# --- Error codes ---


class ErrorCodes:
    """Standardized error codes."""

    INVALID_ENVELOPE = "INVALID_ENVELOPE"
    MISSING_MESSAGE = "MISSING_MESSAGE"
    INVALID_BASE64 = "INVALID_BASE64"
    MISSING_ATTRIBUTES = "MISSING_ATTRIBUTES"
    PROCESSING_ERROR = "PROCESSING_ERROR"
