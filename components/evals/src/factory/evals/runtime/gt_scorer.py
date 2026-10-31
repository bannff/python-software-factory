"""Deterministic GT scorer — computes P/R/F1 from findings vs GT.

No LLM needed. Match keys are parameterized via ``match_on`` so the same
algorithm covers DAST (CWE + method + path), SAST (CWE + file), and any
mix in between. Greedy 1:1 match → precision/recall/F1. Path parameters
are normalized ({id}, <id>, :id → {param}) for fuzzy matching.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_PARAM_RE = re.compile(r"(<[^>]+>|:[a-zA-Z_]+|\{[^}]+\})")
_DEFAULT_MATCH_ON: tuple[str, ...] = ("cwe", "file", "method", "path")
_HTTP_METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")


def _normalize_path(path: str) -> str:
    """Normalize path parameters to canonical form."""
    return _PARAM_RE.sub("{param}", path.rstrip("/").lower())


def _normalize_cwe(raw: str) -> str:
    cwe = (raw or "").upper()
    if cwe and not cwe.startswith("CWE-"):
        cwe = f"CWE-{cwe}"
    return cwe


def _split_resource(resource: str) -> tuple[str, str]:
    """Split a 'GET /api/users' resource string into (method, path)."""
    if not resource or " " not in resource:
        return "", resource or ""
    head, tail = resource.split(" ", 1)
    if head.upper() in _HTTP_METHODS:
        return head.upper(), tail
    return "", resource


def _extract_finding(f: dict[str, Any], key: str) -> str | None:
    """Extract a single match-key value from a finding dict."""
    if key == "cwe":
        return _normalize_cwe(f.get("cwe") or "") or None
    if key == "file":
        fname = Path(f.get("file") or "").name
        return fname or None
    if key == "method":
        method = (f.get("method") or f.get("http_method") or "").upper()
        if not method:
            method, _ = _split_resource(f.get("resource") or f.get("endpoint") or "")
        return method or None
    if key == "path":
        path = f.get("path") or ""
        if not path:
            _, path = _split_resource(f.get("resource") or f.get("endpoint") or "")
        return _normalize_path(path) if path else None
    return None


def _extract_gt(gt: dict[str, Any], key: str) -> str | None:
    """Extract a single match-key value from a GT entry dict."""
    if key == "cwe":
        return _normalize_cwe(gt.get("cwe") or "") or None
    if key == "file":
        # Prefer top-level file, fall back to first code_evidence location.
        fname = Path(gt.get("file") or "").name
        if fname:
            return fname
        for loc in (gt.get("code_evidence", {}) or {}).get("locations", []) or []:
            cand = Path(loc.get("file") or "").name
            if cand:
                return cand
        return None
    artifact = gt.get("artifact") or {}
    if key == "method":
        return (artifact.get("method") or "").upper() or None
    if key == "path":
        path = artifact.get("path") or ""
        return _normalize_path(path) if path else None
    return None


def _build_key(
    extractor,
    entry: dict[str, Any],
    match_on: tuple[str, ...],
) -> tuple[str, ...] | None:
    """Build a tuple key from an entry; None when entry has no match keys."""
    parts: list[str] = []
    any_present = False
    for key in match_on:
        val = extractor(entry, key)
        if val:
            any_present = True
            parts.append(val)
        else:
            parts.append("")
    return tuple(parts) if any_present else None


def score(
    findings: list[dict[str, Any]],
    gt_entries: list[dict[str, Any]],
    match_on: tuple[str, ...] = _DEFAULT_MATCH_ON,
) -> dict[str, Any]:
    """Score findings against GT entries. Returns P/R/F1.

    Args:
        findings: Agent findings (from graph ProvenExploit/Finding entities).
        gt_entries: Ground truth entries (from gt_entries.json).
        match_on: Field keys to combine into the per-entry tuple key. Empty
            extractions are kept in the tuple as ``""`` so a finding/gt that
            only declares some of the keys still matches against another
            entry that declares the same subset. Findings missing ALL keys
            count as false positives; GT entries missing all keys are not
            eligible to be matched (skipped).

    Returns:
        Dict with precision, recall, f1, matched, missed, false_positives,
        true_positives count, etc. Shape preserved across all match_on values.
    """
    match_on = _DEFAULT_MATCH_ON if match_on is None else tuple(match_on)

    gt_map: dict[tuple[str, ...], dict[str, Any]] = {}
    for gt in gt_entries:
        key = _build_key(_extract_gt, gt, match_on)
        if key is None:
            continue
        # First-write-wins keeps behavior deterministic if duplicates exist.
        gt_map.setdefault(key, gt)

    matched: list[dict[str, Any]] = []
    false_pos: list[dict[str, Any]] = []
    matched_keys: set[tuple[str, ...]] = set()

    for f in findings:
        fk = _build_key(_extract_finding, f, match_on)
        if fk is None:
            false_pos.append(f)
            continue
        if fk in gt_map and fk not in matched_keys:
            matched.append({"finding": f, "gt": gt_map[fk]})
            matched_keys.add(fk)
        else:
            false_pos.append(f)

    missed = [gt for k, gt in gt_map.items() if k not in matched_keys]
    tp, fp, fn = len(matched), len(false_pos), len(missed)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    return {
        "precision": round(p, 4),
        "recall": round(r, 4),
        "f1": round(f1, 4),
        "true_positives": tp,
        "false_positives_count": fp,
        "false_negatives": fn,
        "matched": matched,
        "missed": missed,
        "false_positives": false_pos,
    }


# ---------------------------------------------------------------------------
# Backwards-compat private helpers (used by existing tests).
# ---------------------------------------------------------------------------


def _finding_key(f: dict[str, Any]) -> tuple[str, str, str]:
    """Legacy DAST key (cwe, method, path) — preserved for tests."""
    return (
        _extract_finding(f, "cwe") or "",
        _extract_finding(f, "method") or "",
        _extract_finding(f, "path") or "",
    )


def _gt_key(gt: dict[str, Any]) -> tuple[str, str, str]:
    """Legacy DAST GT key (cwe, method, path) — preserved for tests."""
    return (
        _extract_gt(gt, "cwe") or "",
        _extract_gt(gt, "method") or "",
        _extract_gt(gt, "path") or "",
    )
