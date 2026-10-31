"""Bounded, secret-safe projections for the Test MCP facade."""
from __future__ import annotations

import secrets
from pathlib import Path, PureWindowsPath
from typing import Any

from .mcp_redaction import normalize_junit_identity, redact, safe_relative_path
from .ports import TestDiscoveryResult, TestResult

_MAX_OUTPUT, _MAX_ITEMS, _MAX_DIAGNOSTICS = 2_000, 100, 20
_MAX_REDACTION_INPUT = 64_000


def safe_config_label(value: object) -> str:
    """Expose configuration locations without disclosing host paths."""
    text = str(value)
    windows = PureWindowsPath(text)
    return text if not Path(text).is_absolute() and not windows.is_absolute() and not windows.drive else "<configured>"


def rejected_discovery(code: str) -> dict[str, Any]:
    return {"target": "<rejected>", "test_files": [], "test_count": 0,
            "errors": [code], "diagnostics": [code]}


def rejected_execution(code: str) -> dict[str, Any]:
    return {"execution_id": secrets.token_urlsafe(16), "target": "<rejected>",
            "outcome": "invalid_target", "success": False, "error": code,
            "errors": [code], "diagnostics": [code]}


def rejected_junit(code: str) -> dict[str, Any]:
    empty = {"total": 0, "outcomes": {}}
    entry = {"identity": "<report>", "phase": "collection", "baseline_outcome": "unknown",
             "candidate_outcome": "unknown", "reason": code}
    return {"base_report": "<rejected>", "candidate_report": "<rejected>", "passed": False,
            "base": empty, "candidate": empty, "blocking": [entry], "legacy": [],
            "resolved": [], "errors": [code], "regressions": 1, "resolved_count": 0,
            "unchanged": 0, "parse_errors": 0}


def execution(root: Path, target: Path, result: TestResult, *,
              component: str | None = None, path: str | None = None) -> dict[str, Any]:
    errors, diagnostics_truncated = _error_codes(result.errors)
    if "target_not_found" in errors:
        outcome, error = "missing_target", "target_not_found"
    elif "timeout" in errors:
        outcome, error = "timeout", "timeout"
    elif errors:
        outcome, error = "error", errors[0]
    elif result.failed:
        outcome, error = "failed", "test_failures"
    else:
        outcome, error = "passed", None
    output, output_truncated = _bounded(root, result.output)
    files, files_truncated = result_files(root, result.test_files)
    return {"execution_id": secrets.token_urlsafe(16), "target": relative(root, target),
            "outcome": outcome, "success": outcome == "passed", "passed": result.passed,
            "failed": result.failed, "skipped": result.skipped, "total": result.total,
            "duration": round(min(max(result.duration, 0.0), 300.0), 3), "output": output,
            "output_truncated": output_truncated, "errors": errors, "test_files": files,
            "test_files_truncated": files_truncated, "diagnostics": errors,
            "diagnostics_truncated": diagnostics_truncated, "error": error,
            "component": redact(root, component) if component is not None else None,
            "path": redact(root, path) if path is not None else None}


def discovery(root: Path, target: Path, result: TestDiscoveryResult) -> dict[str, Any]:
    errors, diagnostics_truncated = _error_codes(result.errors)
    files, files_truncated = result_files(root, result.test_files)
    return {"target": relative(root, target), "test_files": files,
            "test_count": max(result.test_count, 0), "errors": errors,
            "diagnostics": errors, "test_files_truncated": files_truncated,
            "diagnostics_truncated": diagnostics_truncated}


def junit(root: Path, base: Path, candidate: Path, result: dict[str, Any]) -> dict[str, Any]:
    blocking, blocking_truncated, blocking_total = _entries(root, result.get("blocking"))
    legacy, legacy_truncated, legacy_total = _entries(root, result.get("legacy"))
    resolved, resolved_truncated, resolved_total = _entries(root, result.get("resolved"))
    raw_errors = result.get("errors")
    raw_errors = raw_errors if isinstance(raw_errors, list) else []
    missing = any("target_not_found" in str(item) for item in raw_errors)
    errors = ["target_not_found"] if missing else ["invalid_report"] if raw_errors else []
    if missing and not blocking:
        blocking = [_report_entry("target_not_found")]
        blocking_total = 1
        blocking_truncated = False
    return {"base_report": relative(root, base), "candidate_report": relative(root, candidate),
            "passed": bool(result.get("passed", False)) and not errors,
            "base": _summary(result.get("base")), "candidate": _summary(result.get("candidate")),
            "blocking": blocking, "legacy": legacy, "resolved": resolved, "errors": errors,
            "blocking_truncated": blocking_truncated, "legacy_truncated": legacy_truncated,
            "resolved_truncated": resolved_truncated, "errors_truncated": len(raw_errors) > _MAX_DIAGNOSTICS,
            "regressions": blocking_total, "resolved_count": resolved_total,
            "unchanged": legacy_total, "parse_errors": 0 if missing else len(errors)}


def relative(root: Path, target: Path) -> str:
    value = str(target.relative_to(root)) or "."
    return redact(root, value)


def result_files(root: Path, values: Any) -> tuple[list[str], bool]:
    files: list[str] = []
    for index, item in enumerate(values or []):
        if index >= _MAX_ITEMS * 10:
            return files, True
        value = safe_relative_path(root, str(item))
        if value is None:
            continue
        value = redact(root, value)
        if value in files:
            continue
        if len(files) >= _MAX_ITEMS:
            return files, True
        files.append(value)
    return files, False


def _error_codes(values: Any) -> tuple[list[str], bool]:
    codes: list[str] = []
    for index, item in enumerate(values or []):
        if index >= _MAX_DIAGNOSTICS:
            return codes, True
        text = str(item).lower()
        code = ("target_not_found" if "target_not_found" in text or "not found" in text or "does not exist" in text
                else "timeout" if "timed out" in text or "timeout" in text else "adapter_error")
        if code not in codes:
            codes.append(code)
        if len(codes) > _MAX_DIAGNOSTICS:
            return codes[:_MAX_DIAGNOSTICS], True
    return codes, False


def _summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"total": 0, "outcomes": {}}
    raw_outcomes = value.get("outcomes")
    raw_outcomes = raw_outcomes if isinstance(raw_outcomes, dict) else {}
    outcomes: dict[str, int] = {}
    for key, count in raw_outcomes.items():
        if len(outcomes) >= 20:
            break
        try:
            outcomes[str(key)] = max(int(count), 0)
        except (TypeError, ValueError):
            continue
    return {"total": max(int(value.get("total", 0)), 0), "outcomes": outcomes,
            "outcomes_truncated": len(raw_outcomes) > len(outcomes)}


def _entries(root: Path, values: Any) -> tuple[list[dict[str, str]], bool, int]:
    if not isinstance(values, list):
        return [], False, 0
    entries: list[dict[str, str]] = []
    keys = ("identity", "phase", "baseline_outcome", "candidate_outcome", "reason")
    for value in values[:_MAX_ITEMS]:
        if isinstance(value, dict):
            entries.append({key: _safe_identity(root, str(value.get(key, ""))) if key == "identity"
                            else redact(root, str(value.get(key, ""))) for key in keys})
    return entries, len(values) > _MAX_ITEMS, len(values)


def _safe_identity(root: Path, identity: str) -> str:
    return redact(root, normalize_junit_identity(root, identity))


def _report_entry(reason: str) -> dict[str, str]:
    return {"identity": "<report>", "phase": "collection", "baseline_outcome": "unknown",
            "candidate_outcome": "unknown", "reason": reason}


def _bounded(root: Path, text: Any) -> tuple[str, bool]:
    raw = str(text)
    value = redact(root, raw[:_MAX_REDACTION_INPUT])
    return value[:_MAX_OUTPUT], len(raw) > _MAX_OUTPUT or len(value) > _MAX_OUTPUT
