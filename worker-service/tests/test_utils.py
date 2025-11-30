"""
Tests for Worker Service - Utility functions
"""

import pytest
from utils import redact_sensitive_data


class TestRedaction:
    """Tests for redact_sensitive_data function."""

    def test_redacts_phone_number_with_dashes(self):
        """Should redact phone numbers like 555-0199."""
        text = "User 555-0199 accessed the system"
        result = redact_sensitive_data(text)
        assert "[REDACTED]" in result
        assert "555-0199" not in result

    def test_redacts_full_phone_number(self):
        """Should redact full phone numbers like 555-123-4567."""
        text = "Call me at 555-123-4567 tomorrow"
        result = redact_sensitive_data(text)
        assert "[REDACTED]" in result
        assert "555-123-4567" not in result

    def test_redacts_phone_with_parentheses(self):
        """Should redact phone numbers like (555) 123-4567."""
        text = "Contact: (555) 123-4567"
        result = redact_sensitive_data(text)
        assert "[REDACTED]" in result
        assert "(555) 123-4567" not in result

    def test_redacts_ip_address(self):
        """Should redact IP addresses like 192.168.1.1."""
        text = "Connection from 192.168.1.1 detected"
        result = redact_sensitive_data(text)
        assert "[REDACTED]" in result
        assert "192.168.1.1" not in result

    def test_redacts_email_address(self):
        """Should redact email addresses."""
        text = "Email sent to user@example.com"
        result = redact_sensitive_data(text)
        assert "[REDACTED]" in result
        assert "user@example.com" not in result

    def test_redacts_ssn(self):
        """Should redact SSN patterns like 123-45-6789."""
        text = "SSN: 123-45-6789"
        result = redact_sensitive_data(text)
        assert "[REDACTED]" in result
        assert "123-45-6789" not in result

    def test_preserves_non_sensitive_text(self):
        """Should preserve text without sensitive data."""
        text = "User logged in successfully"
        result = redact_sensitive_data(text)
        assert result == text

    def test_redacts_multiple_items(self):
        """Should redact multiple sensitive items in same text."""
        text = "User 555-0199 from 203.0.113.42 emailed admin@test.com"
        result = redact_sensitive_data(text)
        assert result.count("[REDACTED]") == 3
        assert "555-0199" not in result
        assert "203.0.113.42" not in result
        assert "admin@test.com" not in result

    def test_matches_pdf_example(self):
        """Should match the PDF example output."""
        text = "User 555-0199 accessed the system"
        result = redact_sensitive_data(text)
        assert "User [REDACTED] accessed the system" == result
