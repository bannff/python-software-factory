"""Deterministic canonical JSON and SHA-256 operations for ScenarioPack."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .scenario_models import ScenarioPack, ScenarioPackDraft
from .scenario_validation import validate_scenario_pack

_SET_LIKE = ("sources", "evidence", "claims", "assumptions", "outcomes", "scenarios")
_ID_FIELDS = {
    "sources": "source_id", "evidence": "evidence_id", "claims": "claim_id",
    "assumptions": "assumption_id", "outcomes": "outcome_id", "scenarios": "scenario_id",
}


def scenario_pack_body(pack: ScenarioPackDraft | ScenarioPack) -> dict[str, Any]:
    body = pack.model_dump(mode="json", exclude={"digest"})
    for field in _SET_LIKE:
        body[field] = sorted(body[field], key=lambda item: item[_ID_FIELDS[field]])
    for claim in body["claims"]:
        claim["evidence_ids"] = sorted(claim["evidence_ids"])
    for scenario in body["scenarios"]:
        for field in ("claim_ids", "assumption_ids", "outcome_ids"):
            scenario[field] = sorted(scenario[field])
    return body


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def scenario_pack_digest(pack: ScenarioPackDraft | ScenarioPack) -> str:
    validate_scenario_pack(pack)
    return hashlib.sha256(canonical_json(scenario_pack_body(pack))).hexdigest()


def build_scenario_pack(draft: ScenarioPackDraft) -> ScenarioPack:
    body = scenario_pack_body(draft)
    digest = hashlib.sha256(canonical_json(body)).hexdigest()
    return ScenarioPack.model_validate({**body, "digest": digest})


def scenario_pack_bytes(pack: ScenarioPack) -> bytes:
    digest = scenario_pack_digest(pack)
    if digest != pack.digest:
        raise ValueError("ScenarioPack digest does not match canonical content")
    return canonical_json({**scenario_pack_body(pack), "digest": pack.digest})


def parse_scenario_pack(content: bytes) -> ScenarioPack:
    pack = ScenarioPack.model_validate_json(content)
    if scenario_pack_bytes(pack) != content:
        raise ValueError("ScenarioPack bytes are not canonical")
    return pack
