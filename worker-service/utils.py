"""
Memory Machines Backend - Worker Utilities

Text processing utilities including redaction.
"""

import re


def redact_sensitive_data(text: str) -> str:
    """
    Redact sensitive information from text.

    Redacts:
    - Phone numbers (various formats)
    - IP addresses
    - Email addresses
    - SSN patterns

    Args:
        text: Original text content

    Returns:
        Text with sensitive data replaced by [REDACTED]
    """
    redacted = text

    # Phone numbers: 555-0199, (555) 123-4567, 555.123.4567, +1-555-123-4567
    phone_patterns = [
        r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",  # Full phone
        r"\d{3}[-.\s]\d{4}",  # Short format like 555-0199
    ]
    for pattern in phone_patterns:
        redacted = re.sub(pattern, "[REDACTED]", redacted)

    # IP addresses: 192.168.1.1, 203.0.113.42
    ip_pattern = r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
    redacted = re.sub(ip_pattern, "[REDACTED]", redacted)

    # Email addresses
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    redacted = re.sub(email_pattern, "[REDACTED]", redacted)

    # SSN: 123-45-6789
    ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
    redacted = re.sub(ssn_pattern, "[REDACTED]", redacted)

    return redacted
