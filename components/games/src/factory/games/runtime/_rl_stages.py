"""RL pipeline stage helpers: findings collection, GT loading, scoring, type detection.

These functions are imported back into ``workflow_rl`` so test patch paths
(`factory.games.runtime.workflow_rl._collect_findings`, etc.) continue to work.

Findings collection now goes through the typed graph tools
(``graph_graph_get_findings_for_run`` and ``graph_graph_find_entities``)
introduced in bd python-factory-j1lb. The previous Cypher escape hatch
returned the ``cypher_not_supported`` envelope on networkx (local dev),
which silently produced empty results. Tracked under bd python-factory-ky0i.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from factory.mcp_utils.interface import ToolResult, is_bounded_json, to_plain_json

logger = logging.getLogger(__name__)

_CHALLENGES_DIR = Path("projects/companion_x/challenges")

# bd:python-factory-qer1z — security default. Domain agents (wine, workout, ...)
# may pass count_labels=[...] to override without touching engine code.
DEFAULT_COUNT_LABELS: tuple[str, ...] = ("Finding", "ProvenExploit")


class _SuccessEnvelope(BaseModel):
    """Strict serialized success envelope accepted from the Evals tool."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["v1"]
    ok: Literal[True]
    data: dict[str, JsonValue]
    error: None = None
    idempotency_key: str | None = Field(default=None, max_length=256)


def _collect_findings(
    invoker: Any,
    run_id: str,
    count_labels: Iterable[str] | None = None,
    taxonomy_edges: list[dict] | None = None,
) -> list[dict]:
    """Query graph for consolidated findings from this run.

    Defaults to the security pair ``("Finding", "ProvenExploit")`` for back-compat.
    The "Finding" label, when present, uses the typed
    ``graph_graph_get_findings_for_run`` tool; other labels fall through to
    ``graph_graph_find_entities``. ``None`` taxonomy edges keep the back-compat
    CWE/OCSF default, while ``[]`` skips taxonomy joins.
    """
    labels = tuple(count_labels) if count_labels is not None else DEFAULT_COUNT_LABELS
    if not labels:
        return []
    findings: list[dict] = []
    for label in labels:
        if label == "Finding":
            try:
                kwargs: dict[str, Any] = {
                    "run_id": run_id, "app": "", "limit": 1000,
                }
                if taxonomy_edges is not None:
                    kwargs["taxonomy_edges"] = taxonomy_edges
                result = invoker("graph_graph_get_findings_for_run", **kwargs)
                if result and result.ok and result.data is not None:
                    findings.extend(result.data.rows)
            except Exception as e:
                logger.warning("Finding typed query failed: %s", e)
            continue
        try:
            result = invoker(
                "graph_graph_find_entities",
                entity_type=label,
                properties={"run_id": run_id},
                limit=1000,
            )
            if not result or not result.ok or result.data is None:
                continue
            findings.extend(entity.properties for entity in result.data.entities)
        except Exception as e:
            logger.warning("%s typed query failed: %s", label, e)
    return findings


def _load_gt(target_app: str) -> list[dict]:
    """Load GT entries filtered by target app."""
    if not target_app:
        return []
    gt_file = _CHALLENGES_DIR / target_app / "gt_entries.json"
    if gt_file.exists():
        try:
            return json.loads(gt_file.read_text())
        except Exception:
            pass
    return []


def _score(
    invoker: Any, findings: list[dict], gt_entries: list[dict],
    match_on: list[str] | None = None,
) -> dict[str, Any]:
    """Score findings against GT while preserving ``None`` versus ``[]``."""
    if not gt_entries:
        return {"f1": 0, "error": "No GT entries for target"}
    kwargs: dict[str, Any] = {"findings": findings, "gt_entries": gt_entries}
    if match_on is not None:
        kwargs["match_on"] = match_on
    try:
        result = invoker("evals_evals_score_gt", **kwargs)
        score = _normalize_score_result(result)
        return score if score is not None else {"f1": 0, "error": "Evals score failed"}
    except Exception:
        return {"f1": 0, "error": "Evals score failed"}


def _normalize_score_result(result: Any) -> dict[str, Any] | None:
    """Accept only bounded typed or serialized-v1 Evals success results."""
    envelope = _validated_success_envelope(result)
    if envelope is None:
        return None
    data = envelope.data
    if _contains_error_marker(data):
        return None
    normalized = dict(data)
    if _bounded_score(normalized.get("f1")) is None:
        return None
    for key in ("precision", "recall"):
        if key in normalized and _bounded_score(normalized[key]) is None:
            return None
    return normalized


def _validated_success_envelope(result: Any) -> _SuccessEnvelope | None:
    if isinstance(result, ToolResult):
        if result.schema_version != "v1" or result.ok is not True:
            return None
        try:
            candidate = to_plain_json(result.model_dump(mode="python"))
        except (TypeError, ValueError):
            return None
    elif isinstance(result, Mapping):
        if "schema_version" not in result:
            return None
        candidate = dict(result)
    else:
        return None
    if not is_bounded_json(candidate):
        return None
    try:
        return _SuccessEnvelope.model_validate(candidate)
    except ValidationError:
        return None


def _contains_error_marker(value: Any) -> bool:
    if isinstance(value, Mapping):
        if value.get("error") not in (None, "", False, 0):
            return True
        if "error_count" in value:
            count = value["error_count"]
            if not isinstance(count, int) or isinstance(count, bool) or count != 0:
                return True
        if value.get("label") == "error":
            return True
        return any(_contains_error_marker(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_error_marker(item) for item in value)
    return False


def _bounded_score(value: Any) -> float | None:
    """Return finite scores in the Evals contract range."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        score = float(value)
    except (OverflowError, ValueError):
        return None
    return score if 0.0 <= score <= 1.0 else None
