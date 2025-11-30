"""
Memory Machines Backend - Worker Service Schemas

Pydantic models for request/response validation and Swagger documentation.
"""

from typing import Dict, Optional

from pydantic import BaseModel, Field

# --- Request Models ---


class PubSubMessage(BaseModel):
    """Pub/Sub message structure."""

    data: str = Field(
        ...,
        description="Base64 encoded message data",
    )
    attributes: Dict[str, str] = Field(
        ...,
        description="Message attributes (tenant_id, log_id, source, content_hash)",
    )
    messageId: Optional[str] = Field(
        None,
        description="Pub/Sub message ID",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "data": "VGVzdCBsb2cgbWVzc2FnZQ==",
                "attributes": {
                    "tenant_id": "acme_corp",
                    "log_id": "log-001",
                    "source": "json_upload",
                    "content_hash": "abc123",
                },
                "messageId": "12345",
            }
        }
    }


class PubSubEnvelope(BaseModel):
    """Pub/Sub push request envelope."""

    message: PubSubMessage = Field(
        ...,
        description="The Pub/Sub message",
    )
    subscription: Optional[str] = Field(
        None,
        description="Subscription name",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": {
                    "data": "VGVzdCBsb2cgbWVzc2FnZQ==",
                    "attributes": {
                        "tenant_id": "acme_corp",
                        "log_id": "log-001",
                        "source": "json_upload",
                        "content_hash": "abc123",
                    },
                    "messageId": "12345",
                },
                "subscription": "projects/my-project/subscriptions/worker-push-sub",
            }
        }
    }


# --- Response Models ---


class ErrorResponse(BaseModel):
    """Error response."""

    error: str = Field(
        ...,
        description="Error message",
    )

    model_config = {"json_schema_extra": {"example": {"error": "missing tenant_id or log_id"}}}
