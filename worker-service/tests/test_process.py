"""
Tests for Worker Service - /process endpoint
"""

import base64
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Import app
from main import app

client = TestClient(app)


def create_pubsub_envelope(
    text, tenant_id, log_id, source="json_upload", content_hash="abc123", correlation_id="corr-123"
):
    """Helper to create Pub/Sub push envelope."""
    return {
        "message": {
            "data": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
            "attributes": {
                "tenant_id": tenant_id,
                "log_id": log_id,
                "source": source,
                "content_hash": content_hash,
                "correlation_id": correlation_id,
            },
            "messageId": "test-message-id",
        },
        "subscription": "projects/test/subscriptions/test-sub",
    }


@pytest.fixture
def mock_firestore():
    """Mock Firestore client for each test."""
    mock_db = MagicMock()
    mock_doc_ref = MagicMock()
    mock_doc_ref.get.return_value.exists = False
    mock_db.collection.return_value.document.return_value.collection.return_value.document.return_value = (
        mock_doc_ref
    )

    with patch("api.process.get_db", return_value=mock_db):
        yield {"db": mock_db, "doc_ref": mock_doc_ref}


@pytest.fixture
def mock_sleep():
    """Mock asyncio.sleep to speed up tests."""
    with patch("api.process.asyncio.sleep", return_value=None):
        yield


class TestProcessEndpoint:
    """Tests for /process endpoint."""

    def test_valid_message_returns_200(self, mock_firestore, mock_sleep):
        """Valid Pub/Sub message should return 200."""
        envelope = create_pubsub_envelope(
            text="Test log message", tenant_id="acme_corp", log_id="test-001"
        )
        response = client.post("/process", json=envelope)
        assert response.status_code == 200

    def test_writes_to_correct_firestore_path(self, mock_firestore, mock_sleep):
        """Should write to tenants/{tenant_id}/processed_logs/{log_id}."""
        envelope = create_pubsub_envelope(
            text="Test log message", tenant_id="acme_corp", log_id="test-001"
        )
        client.post("/process", json=envelope)

        mock_db = mock_firestore["db"]
        mock_db.collection.assert_called_with("tenants")
        mock_db.collection.return_value.document.assert_called_with("acme_corp")

    def test_missing_message_returns_400(self, mock_firestore, mock_sleep):
        """Missing 'message' in envelope should return 400."""
        envelope = {"subscription": "test"}
        response = client.post("/process", json=envelope)
        assert response.status_code == 400

    def test_missing_tenant_id_returns_400(self, mock_firestore, mock_sleep):
        """Missing tenant_id attribute should return 400."""
        envelope = {
            "message": {
                "data": base64.b64encode(b"test").decode("utf-8"),
                "attributes": {"log_id": "test-001"},
            }
        }
        response = client.post("/process", json=envelope)
        assert response.status_code == 400

    def test_missing_log_id_returns_400(self, mock_firestore, mock_sleep):
        """Missing log_id attribute should return 400."""
        envelope = {
            "message": {
                "data": base64.b64encode(b"test").decode("utf-8"),
                "attributes": {"tenant_id": "acme_corp"},
            }
        }
        response = client.post("/process", json=envelope)
        assert response.status_code == 400

    def test_invalid_base64_returns_400(self, mock_firestore, mock_sleep):
        """Invalid base64 data should return 400."""
        envelope = {
            "message": {
                "data": "not-valid-base64!!!",
                "attributes": {"tenant_id": "acme_corp", "log_id": "test-001"},
            }
        }
        response = client.post("/process", json=envelope)
        assert response.status_code == 400

    def test_invalid_json_envelope_returns_400(self, mock_firestore, mock_sleep):
        """Invalid JSON envelope should return 400."""
        response = client.post(
            "/process", content="not json", headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400


class TestIdempotency:
    """Tests for idempotency handling."""

    def test_duplicate_message_skipped(self, mock_firestore, mock_sleep):
        """Duplicate message with same content_hash should be skipped."""
        mock_doc_ref = mock_firestore["doc_ref"]

        # Simulate existing doc with same hash
        mock_existing = MagicMock()
        mock_existing.exists = True
        mock_existing.to_dict.return_value = {"content_hash": "abc123"}
        mock_doc_ref.get.return_value = mock_existing

        envelope = create_pubsub_envelope(
            text="Test log message",
            tenant_id="acme_corp",
            log_id="test-001",
            content_hash="abc123",
        )
        response = client.post("/process", json=envelope)

        assert response.status_code == 200
        mock_doc_ref.set.assert_not_called()

    def test_different_hash_processes(self, mock_firestore, mock_sleep):
        """Message with different content_hash should be processed."""
        mock_doc_ref = mock_firestore["doc_ref"]

        # Simulate existing doc with different hash
        mock_existing = MagicMock()
        mock_existing.exists = True
        mock_existing.to_dict.return_value = {"content_hash": "different-hash"}
        mock_doc_ref.get.return_value = mock_existing

        envelope = create_pubsub_envelope(
            text="Test log message",
            tenant_id="acme_corp",
            log_id="test-001",
            content_hash="new-hash",
        )
        response = client.post("/process", json=envelope)

        assert response.status_code == 200
        mock_doc_ref.set.assert_called_once()


class TestTenantIsolation:
    """Tests for tenant isolation."""

    def test_different_tenants_different_paths(self, mock_firestore, mock_sleep):
        """Different tenants should write to different paths."""
        mock_db = mock_firestore["db"]

        # First tenant
        envelope1 = create_pubsub_envelope(
            text="Message 1", tenant_id="acme_corp", log_id="log-001"
        )
        client.post("/process", json=envelope1)

        # Second tenant
        envelope2 = create_pubsub_envelope(text="Message 2", tenant_id="beta_inc", log_id="log-002")
        client.post("/process", json=envelope2)

        # Verify different tenant paths were used
        calls = mock_db.collection.return_value.document.call_args_list
        tenant_ids = [call[0][0] for call in calls]
        assert "acme_corp" in tenant_ids
        assert "beta_inc" in tenant_ids


class TestCorrelationId:
    """Tests for correlation ID handling."""

    def test_correlation_id_stored_in_firestore(self, mock_firestore, mock_sleep):
        """Correlation ID should be stored in Firestore document."""
        mock_doc_ref = mock_firestore["doc_ref"]

        envelope = create_pubsub_envelope(
            text="Test log message",
            tenant_id="acme_corp",
            log_id="test-001",
            correlation_id="my-correlation-id",
        )
        response = client.post("/process", json=envelope)

        assert response.status_code == 200
        mock_doc_ref.set.assert_called_once()
        call_args = mock_doc_ref.set.call_args[0][0]
        assert call_args["correlation_id"] == "my-correlation-id"


class TestProcessingErrors:
    """Tests for processing error handling."""

    def test_firestore_failure_returns_processing_error(self, mock_firestore, mock_sleep):
        """Firestore failures should return 500 with PROCESSING_ERROR."""
        mock_doc_ref = mock_firestore["doc_ref"]
        mock_doc_ref.set.side_effect = Exception("boom")

        envelope = create_pubsub_envelope(
            text="Test log message",
            tenant_id="acme_corp",
            log_id="test-001",
            content_hash="abc123",
        )
        response = client.post("/process", json=envelope)
        body = response.json()

        assert response.status_code == 500
        assert body["success"] is False
        assert body["error"]["code"] == "PROCESSING_ERROR"
        assert body["error"]["message"] == "failed to persist processed log"
