"""Shared correlation helpers for cross-brick activity and graph linking."""

from __future__ import annotations

from typing import Any

from .context import get_envelope

_CANONICAL_KEYS = (
    "correlation_id", "request_id", "trace_id", "span_id", "tracestate",
    "parent_span_id", "tenant_id", "principal_id", "session_id", "agent_id",
    "run_id", "graph_id", "entity_id", "env_id", "game_id", "target_app",
    "node_id", "workflow_type", "vuln_class", "domain_class",
)

_ALIASES = {"workflow_run_id": "run_id", "request_id": "correlation_id"}
_NESTED_KEYS = ("config", "payload", "metadata", "attributes", "context")


def normalize_correlation(
    *sources: Any, authoritative_run_id: Any = None,
) -> dict[str, str]:
    """Normalize correlation, rejecting run conflicts unless authority is explicit."""
    authoritative = _normalize_scalar(authoritative_run_id)
    correlation = _trusted_correlation()
    if authoritative:
        correlation.pop("run_id", None)
    normalized = _with_correlation(
        _normalize_sources(
            [get_envelope(), *sources], authoritative_run_id=authoritative or None,
        )
    )
    for key, value in normalized.items():
        correlation.setdefault(key, value)
    if authoritative:
        correlation["run_id"] = authoritative
    return correlation


def merge_correlation_fields(
    payload: dict[str, Any], *sources: Any, authoritative_run_id: Any = None,
) -> dict[str, Any]:
    """Enrich payload without letting ambient state replace owned run authority."""
    merged = dict(payload)
    authoritative = _normalize_scalar(authoritative_run_id)
    trusted = _trusted_correlation()
    if authoritative:
        trusted.pop("run_id", None)
    normalized = normalize_correlation(
        payload, *sources, authoritative_run_id=authoritative or None,
    )
    for key, value in normalized.items():
        if key in trusted:
            merged[key] = trusted[key]
        else:
            merged.setdefault(key, value)
    if authoritative:
        merged["run_id"] = authoritative
    elif trusted.get("correlation_id") and "request_id" in merged:
        merged["request_id"] = trusted["correlation_id"]
    merged.pop("workflow_run_id", None)
    return merged


def correlation_attributes(
    *sources: Any, authoritative_run_id: Any = None,
) -> dict[str, str | int | float | bool]:
    """Return strict scalar attributes for event-history metadata."""
    correlation = normalize_correlation(
        *sources, authoritative_run_id=authoritative_run_id,
    )
    return {key: value for key, value in correlation.items() if _is_strict_scalar(value)}


def build_event_publish_input(
    payload: dict[str, Any], *sources: Any, authoritative_run_id: Any = None,
) -> dict[str, Any]:
    """Build canonical events input, optionally owning the durable run ID."""
    merged_payload = merge_correlation_fields(
        payload, *sources, authoritative_run_id=authoritative_run_id,
    )
    correlation = normalize_correlation(
        merged_payload, *sources, authoritative_run_id=authoritative_run_id,
    )
    publish_input: dict[str, Any] = {
        "payload": merged_payload,
        "attributes": correlation_attributes(
            merged_payload, *sources, authoritative_run_id=authoritative_run_id,
        ),
    }
    for key in ("tenant_id", "principal_id", "session_id"):
        if correlation.get(key):
            publish_input[key] = correlation[key]
    if correlation.get("correlation_id"):
        publish_input["request_id"] = correlation["correlation_id"]
    return publish_input


def _trusted_correlation() -> dict[str, str]:
    return _with_correlation(_normalize_sources([get_envelope()]))


def _with_correlation(correlation: dict[str, str]) -> dict[str, str]:
    if "correlation_id" not in correlation:
        for key in ("request_id", "run_id", "graph_id", "env_id", "game_id", "session_id"):
            if correlation.get(key):
                correlation["correlation_id"] = correlation[key]
                break
    return correlation


def _normalize_sources(
    sources: list[Any], *, authoritative_run_id: str | None = None,
) -> dict[str, str]:
    correlation: dict[str, str] = {}
    run_id: str | None = authoritative_run_id
    for source in sources:
        for mapping in _iter_mappings(source):
            for key, value in mapping.items():
                canonical_key = _ALIASES.get(str(key), str(key))
                if canonical_key not in _CANONICAL_KEYS:
                    continue
                normalized_value = _normalize_scalar(value)
                if not normalized_value:
                    continue
                if canonical_key == "run_id":
                    if authoritative_run_id is not None:
                        continue
                    if run_id is not None and run_id != normalized_value:
                        raise ValueError("conflicting run_id/workflow_run_id")
                    run_id = run_id or normalized_value
                    continue
                correlation.setdefault(canonical_key, normalized_value)
    if run_id is not None:
        correlation["run_id"] = run_id
    return correlation


def _iter_mappings(source: Any) -> list[dict[str, Any]]:
    if not isinstance(source, dict):
        return []
    mappings = [source]
    for key in _NESTED_KEYS:
        nested = source.get(key)
        if isinstance(nested, dict):
            mappings.append(nested)
    return mappings


def _normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def _is_strict_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))
