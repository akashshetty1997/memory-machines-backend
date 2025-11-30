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
            "example": {"code": "VALIDATION_ERROR", "message": "tenant_id required"}
        }
    }


class APIResponse(BaseModel):
    """Standardized API response structure."""

    success: bool = Field(..., description="Whether the request was successful")
    data: Optional[Any] = Field(None, description="Response data on success")
    error: Optional[ErrorDetail] = Field(None, description="Error details on failure")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "data": {"log_id": "log-001", "status": "accepted"},
                "error": None,
            }
        }
    }


class IngestData(BaseModel):
    """Data returned on successful ingestion."""

    status: str = Field(..., description="Status of the request")
    log_id: str = Field(..., description="Log ID for tracking")

    model_config = {"json_schema_extra": {"example": {"status": "accepted", "log_id": "log-001"}}}


# --- Helper functions ---


def success_response(data: Any, status_code: int = 200) -> tuple[dict, int]:
    """Create a success response."""
    return {"success": True, "data": data, "error": None}, status_code


def error_response(code: str, message: str, status_code: int = 400) -> tuple[dict, int]:
    """Create an error response."""
    return {
        "success": False,
        "data": None,
        "error": {"code": code, "message": message},
    }, status_code


# --- Error codes ---


class ErrorCodes:
    """Standardized error codes."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_JSON = "INVALID_JSON"
    UNSUPPORTED_CONTENT_TYPE = "UNSUPPORTED_CONTENT_TYPE"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
