"""Normalized protected-field aliases shared by persistence and telemetry."""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

SENSITIVE_FIELDS = frozenset({
    "api_key", "apikey", "attachment", "attachments", "authentication",
    "authorization", "bcc", "bcc_address", "bcc_addresses", "bearer", "body",
    "cc", "cc_address", "cc_addresses", "client_secret", "content", "cookie",
    "credential", "credentials", "html", "html_body", "message", "message_body",
    "password", "passwd", "payload", "private_key", "provider_request",
    "provider_request_body", "provider_response", "provider_response_body", "query",
    "raw", "raw_evidence", "recipient", "recipient_address", "recipient_addresses",
    "recipient_list", "recipients", "refresh_token", "secret", "session_token",
    "set_cookie", "subject", "subject_line", "text", "text_body", "to",
    "to_address", "to_addresses", "token", "access_token",
})
INLINE_SENSITIVE_FIELDS = SENSITIVE_FIELDS - {"content"}
EXCEPTION_FIELDS = frozenset({
    "error", "error_message", "exception", "exception_message", "exception_text",
    "stack_trace", "traceback",
})


def plain(value: Any) -> Any:
    return value.model_dump(mode="json") if isinstance(value, BaseModel) else value


def field_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", value)
    return re.sub(r"[^A-Za-z0-9]+", "_", snake).strip("_").lower()


def sensitive_key(key: Any, fields: frozenset[str] = SENSITIVE_FIELDS) -> bool:
    return field_name(key) in fields


__all__ = [
    "EXCEPTION_FIELDS", "INLINE_SENSITIVE_FIELDS", "SENSITIVE_FIELDS",
    "field_name", "plain", "sensitive_key",
]
