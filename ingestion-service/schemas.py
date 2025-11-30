"""
Memory Machines Backend - Ingestion Service Schemas

Pydantic models for request/response validation and Swagger documentation.
"""

from typing import Optional

from pydantic import BaseModel, Field

# --- Request Models ---


class IngestJSONRequest(BaseModel):
    """JSON request body for /ingest endpoint."""

    tenant_id: str = Field(
        ...,
        description="Unique identifier for the tenant",
    )
    log_id: str = Field(
        ...,
        description="Unique identifier for this log entry",
    )
    text: str = Field(
        ...,
        description="Log text content (max 5000 characters)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "tenant_id": "acme_corp",
                "log_id": "log-001",
                "text": "User 555-0199 accessed the system at 10:00 AM",
            }
        }
    }


# --- Response Models ---


class IngestSuccessResponse(BaseModel):
    """Successful ingestion response."""

    status: str = Field(
        ...,
        description="Status of the request",
    )
    log_id: str = Field(
        ...,
        description="Log ID for tracking",
    )

    model_config = {"json_schema_extra": {"example": {"status": "accepted", "log_id": "log-001"}}}


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(
        ...,
        description="Error message",
    )

    model_config = {"json_schema_extra": {"example": {"error": "tenant_id required"}}}
