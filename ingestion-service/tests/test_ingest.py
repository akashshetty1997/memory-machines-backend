"""
Tests for Ingestion Service - /ingest endpoint
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Create mock before importing app
mock_publisher = MagicMock()
mock_publisher.topic_path.return_value = "projects/test/topics/test-topic"
mock_future = MagicMock()
mock_publisher.publish.return_value = mock_future


@pytest.fixture(autouse=True)
def mock_pubsub():
    """Mock Pub/Sub client for all tests."""
    with patch("api.ingest.get_publisher", return_value=mock_publisher):
        yield mock_publisher


# Import app after setting up mocks
from main import app

client = TestClient(app)


class TestJSONIngestion:
    """Tests for JSON payload ingestion."""

    def test_valid_json_returns_202(self, mock_pubsub):
        """Valid JSON request should return 202 Accepted."""
        payload = {
            "tenant_id": "acme_corp",
            "log_id": "test-001",
            "text": "Test log message",
        }
        response = client.post(
            "/ingest", json=payload, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 202
        assert response.json()["success"] is True
        assert response.json()["data"]["status"] == "accepted"
        assert response.json()["data"]["log_id"] == "test-001"
        assert "correlation_id" in response.json()["data"]
        assert response.json()["error"] is None

    def test_request_id_header_is_used_as_correlation_id(self, mock_pubsub):
        """X-Request-Id header should be used as correlation_id."""
        payload = {"tenant_id": "acme_corp", "log_id": "test-001", "text": "Test log message"}
        response = client.post(
            "/ingest",
            json=payload,
            headers={"Content-Type": "application/json", "X-Request-Id": "my-custom-request-id"},
        )
        assert response.status_code == 202
        assert response.json()["data"]["correlation_id"] == "my-custom-request-id"

    def test_missing_tenant_id_returns_400(self, mock_pubsub):
        """Missing tenant_id should return 400."""
        payload = {"log_id": "test-001", "text": "Test log message"}
        response = client.post("/ingest", json=payload)
        assert response.status_code == 400
        assert response.json()["success"] == False
        assert response.json()["data"] is None
        assert "tenant_id" in response.json()["error"]["message"]
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_missing_log_id_returns_400(self, mock_pubsub):
        """Missing log_id should return 400."""
        payload = {"tenant_id": "acme_corp", "text": "Test log message"}
        response = client.post("/ingest", json=payload)
        assert response.status_code == 400
        assert response.json()["success"] == False
        assert "log_id" in response.json()["error"]["message"]

    def test_missing_text_returns_400(self, mock_pubsub):
        """Missing text should return 400."""
        payload = {"tenant_id": "acme_corp", "log_id": "test-001"}
        response = client.post("/ingest", json=payload)
        assert response.status_code == 400
        assert response.json()["success"] == False
        assert "text" in response.json()["error"]["message"]

    def test_invalid_json_returns_400(self, mock_pubsub):
        """Invalid JSON should return 400."""
        response = client.post(
            "/ingest",
            content="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert response.json()["success"] == False
        assert response.json()["error"]["code"] == "INVALID_JSON"


class TestTextPlainIngestion:
    """Tests for text/plain payload ingestion."""

    def test_valid_text_returns_202(self, mock_pubsub):
        """Valid text/plain request should return 202 Accepted."""
        response = client.post(
            "/ingest",
            content="Test log message",
            headers={"Content-Type": "text/plain", "X-Tenant-ID": "acme_corp"},
        )
        assert response.status_code == 202
        assert response.json()["success"] is True
        assert response.json()["data"]["status"] == "accepted"
        assert "log_id" in response.json()["data"]
        assert "correlation_id" in response.json()["data"]

    def test_missing_tenant_header_returns_400(self, mock_pubsub):
        """Missing X-Tenant-ID header should return 400."""
        response = client.post(
            "/ingest",
            content="Test log message",
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 400
        assert response.json()["success"] == False
        assert "X-Tenant-ID" in response.json()["error"]["message"]

    def test_empty_text_returns_400(self, mock_pubsub):
        """Empty text body should return 400."""
        response = client.post(
            "/ingest",
            content="",
            headers={"Content-Type": "text/plain", "X-Tenant-ID": "acme_corp"},
        )
        assert response.status_code == 400
        assert response.json()["success"] == False
        assert "text" in response.json()["error"]["message"]


class TestContentType:
    """Tests for Content-Type handling."""

    def test_unsupported_content_type_returns_415(self, mock_pubsub):
        """Unsupported Content-Type should return 415."""
        response = client.post(
            "/ingest",
            content="<xml>data</xml>",
            headers={"Content-Type": "application/xml"},
        )
        assert response.status_code == 415
        assert response.json()["success"] == False
        assert response.json()["error"]["code"] == "UNSUPPORTED_CONTENT_TYPE"


class TestPayloadLimits:
    """Tests for payload size limits."""

    def test_text_exceeds_limit_returns_413(self, mock_pubsub):
        """Text exceeding 5000 chars should return 413."""
        payload = {"tenant_id": "acme_corp", "log_id": "test-001", "text": "x" * 5001}
        response = client.post("/ingest", json=payload)
        assert response.status_code == 413
        assert response.json()["success"] == False
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    def test_text_at_limit_returns_202(self, mock_pubsub):
        """Text at exactly 5000 chars should return 202."""
        payload = {"tenant_id": "acme_corp", "log_id": "test-001", "text": "x" * 5000}
        response = client.post("/ingest", json=payload)
        assert response.status_code == 202
        assert response.json()["success"] == True
