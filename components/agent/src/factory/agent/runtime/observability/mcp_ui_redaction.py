"""Redact mcp-ui UIResource bodies from logs + OTel spans (bd-0x2jq).

Threat T9 (verdict ``d580bfdd-8928-47a4-8d73-a899328e128e``). With
``FactoryMCPClient`` (bd-nmzlk) shipped, ``EmbeddedResource.uri`` +
``mimeType`` + ``text`` body now flow through Strands' content
flatten — backend logs / OTel exporters see attacker-controlled
HTML/JS bodies BEFORE the FE does. Risks: (1) PII exfil via
prompt-injected body content, (2) indexed XSS in CloudWatch /
OpenSearch dashboards.

Mitigation: redact ``text`` of any block whose ``mimeType`` matches
the mcp-ui danger list to ``{uri, mimeType, size, sha256}``. Plain
``TextContent`` and image content pass through unchanged. Hard gate
for ``bd:python-factory-lo1g9.4``. Out of scope: UIResourceRenderer,
agent prompt teaching, FE iframe sandbox/CSP. Pure-stdlib; never
raises out of the filter callback.
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import re
from typing import Any

# Single-prefix MIME danger list. Prefix-match catches
# ``text/html;profile=mcp-app`` alongside bare ``text/html``.
_DANGER_MIME_PREFIXES: tuple[str, ...] = (
    "text/html", "application/vnd.mcp-ui.", "text/uri-list",
)
_MIME_PROBE_RE = re.compile(
    r"(?:text/html|application/vnd\.mcp-ui\.|text/uri-list)",
    flags=re.IGNORECASE,
)
# Last-ditch: scrub ``"text": "..."`` accompanied by a danger MIME
# marker. Used only when JSON parsing has already failed; conservative.
_SAFE_STRIP_RE = re.compile(
    r'"text"\s*:\s*"(?:[^"\\]|\\.)*"', flags=re.DOTALL,
)
_INSTALLED = False
_TARGET_LOGGER_NAMES: tuple[str, ...] = (
    "", "factory", "factory.agent", "factory.api", "factory.ui",
    "strands", "strands.tools.mcp", "strands.telemetry",
    "uvicorn", "uvicorn.error", "uvicorn.access",
)
logger = logging.getLogger(__name__)


def _is_danger_mime(mime: str | None) -> bool:
    if not mime or not isinstance(mime, str):
        return False
    lower = mime.lower()
    return any(lower.startswith(p) for p in _DANGER_MIME_PREFIXES)


def redact_mcp_ui_block(block: Any) -> Any:
    """Pure: redact a single tool_result content block.

    Dict + danger MIME + ``text`` field → return a new dict with
    ``text`` replaced by ``{uri, mimeType, size, sha256}``. Otherwise
    return unchanged.
    """
    if not isinstance(block, dict):
        return block
    mime = block.get("mimeType")
    if not _is_danger_mime(mime):
        return block
    text = block.get("text")
    if not isinstance(text, str):
        return block

    raw = text.encode("utf-8", errors="replace")
    redacted: dict[str, Any] = {
        "uri": block.get("uri", ""),
        "mimeType": mime,
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "_factory_redacted": "mcp-ui-body",
    }
    # Preserve scalar metadata; drop nested children that could
    # themselves carry a body.
    for key, value in block.items():
        if key in ("text", "uri", "mimeType"):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            redacted[key] = value
    return redacted


def _walk_and_redact(obj: Any) -> Any:
    """Recursively redact mcp-ui shapes anywhere in ``obj``."""
    if isinstance(obj, dict):
        if _is_danger_mime(obj.get("mimeType")):
            return redact_mcp_ui_block(obj)
        return {k: _walk_and_redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk_and_redact(item) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_walk_and_redact(item) for item in obj)
    return obj


def _maybe_parse_json(text: str) -> Any | None:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def _redact_string_payload(text: str) -> str:
    """Redact mcp-ui shapes embedded in a string log message."""
    parsed = _maybe_parse_json(text)
    if parsed is not None:
        return json.dumps(_walk_and_redact(parsed), default=str)
    if not _MIME_PROBE_RE.search(text):
        return text
    return _SAFE_STRIP_RE.sub('"text": "[redacted-mcp-ui-body]"', text)


class MCPUIRedactionFilter(logging.Filter):
    """``logging.Filter`` that redacts mcp-ui bodies from log records.

    Walks ``record.args`` (``logger.info("got %s", payload)``) and
    ``record.msg`` (``logger.info(json.dumps(payload))``). Always
    returns ``True`` — never drops records. On unexpected failure,
    blanks the body rather than risk a logging-loop or body leak.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        try:
            self._redact_args(record)
            self._redact_msg(record)
        except Exception:  # noqa: BLE001 — never break logging
            record.msg = "[mcp-ui-redaction-error: record dropped]"
            record.args = ()
        return True

    def _redact_args(self, record: logging.LogRecord) -> None:
        if record.args is None:
            return
        if isinstance(record.args, tuple) and record.args:
            record.args = tuple(_walk_and_redact(a) for a in record.args)
            return
        if isinstance(record.args, dict):
            record.args = _walk_and_redact(record.args)

    def _redact_msg(self, record: logging.LogRecord) -> None:
        if not isinstance(record.msg, str):
            if isinstance(record.msg, (dict, list)):
                record.msg = _walk_and_redact(record.msg)
            return
        if _MIME_PROBE_RE.search(record.msg) is None:
            return
        record.msg = _redact_string_payload(record.msg)


def redact_mcp_ui_in_otel_attributes(attrs: dict) -> dict:
    """Redact mcp-ui shapes inside OTel span attributes.

    Strands' ``Tracer.end_tool_call_span`` serializes tool result
    content into ``gen_ai.choice`` events / ``tool.result`` attributes
    (``strands/telemetry/tracer.py:494, 565`` in 1.40.0). Span exporter
    wrappers should call this before serialising.
    """
    if not isinstance(attrs, dict):
        return attrs
    out: dict[str, Any] = {}
    for key, value in attrs.items():
        if isinstance(value, str):
            out[key] = (_redact_string_payload(value)
                        if _MIME_PROBE_RE.search(value) else value)
        else:
            out[key] = _walk_and_redact(copy.deepcopy(value))
    return out


def install_mcp_ui_redaction() -> None:
    """Idempotent: attach ``MCPUIRedactionFilter`` to target loggers."""
    global _INSTALLED
    if _INSTALLED:
        return
    flt = MCPUIRedactionFilter(name="mcp_ui_redaction")
    for name in _TARGET_LOGGER_NAMES:
        target = logging.getLogger(name)
        if not any(getattr(f, "name", "") == "mcp_ui_redaction"
                   for f in target.filters):
            target.addFilter(flt)
    _INSTALLED = True
    logger.debug("mcp_ui_redaction installed on %d loggers",
                 len(_TARGET_LOGGER_NAMES))


__all__ = [
    "MCPUIRedactionFilter",
    "install_mcp_ui_redaction",
    "redact_mcp_ui_block",
    "redact_mcp_ui_in_otel_attributes",
]
