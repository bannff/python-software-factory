"""Exact structural workflow references and persisted-output evidence."""
from __future__ import annotations

import hashlib
import re
from typing import Any, Callable

from .canonical import canonical_json
from .models import ToolTarget

_RUN_REF = re.compile(r"^workflow-run:///input#(/.*)?$")
_STEP_REF = re.compile(
    r"^workflow-step:///([A-Za-z0-9_.-]+)/(output|evidence)#(/.*)?$"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def resolve_pointer(value: Any, pointer: str) -> Any:
    """Resolve one RFC 6901 JSON pointer, with ``''`` selecting the root."""
    if pointer and not pointer.startswith("/"):
        raise ValueError(f"invalid JSON pointer: {pointer}")
    current = value
    for raw in pointer.lstrip("/").split("/") if pointer else ():
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            if not token.isdigit() or int(token) >= len(current):
                raise ValueError(f"invalid list pointer token: {token}")
            current = current[int(token)]
        elif isinstance(current, dict) and token in current:
            current = current[token]
        else:
            raise ValueError(f"unresolved JSON pointer: {pointer}")
    return current


def resolve_refs(
    value: Any, load_output: Callable[[str], Any], *,
    run_input: Any | None = None,
    load_evidence: Callable[[str], Any] | None = None,
) -> Any:
    """Resolve exact one-key run-input or verified step-material references."""
    if isinstance(value, dict):
        if "$ref" in value:
            if set(value) != {"$ref"} or not isinstance(value["$ref"], str):
                raise ValueError("invalid structural reference")
            reference = value["$ref"]
            run_match = _RUN_REF.fullmatch(reference)
            if run_match:
                if run_input is None:
                    raise ValueError("workflow run input is unavailable")
                return resolve_pointer(run_input, run_match.group(1) or "")
            step_match = _STEP_REF.fullmatch(reference)
            if step_match:
                step_id, material, pointer = step_match.groups()
                if material == "evidence":
                    if load_evidence is None:
                        raise ValueError("workflow step evidence is unavailable")
                    source = load_evidence(step_id)
                else:
                    source = load_output(step_id)
                return resolve_pointer(source, pointer or "")
            raise ValueError("invalid workflow structural reference")
        return {
            key: resolve_refs(
                item, load_output, run_input=run_input,
                load_evidence=load_evidence,
            ) for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            resolve_refs(
                item, load_output, run_input=run_input,
                load_evidence=load_evidence,
            ) for item in value
        ]
    return value


def artifact_declarations(output: Any) -> dict[str, Any]:
    """Validate producer-declared digests without claiming byte verification."""
    artifacts = output.get("artifacts", {}) if isinstance(output, dict) else {}
    if artifacts is None:
        artifacts = {}
    if not isinstance(artifacts, dict):
        raise ValueError("artifacts must be an object")
    declarations: dict[str, Any] = {}
    for name, artifact in artifacts.items():
        if not isinstance(artifact, dict):
            raise ValueError(f"artifact {name} must be an object")
        digest = artifact.get("sha256")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise ValueError(f"artifact {name} has invalid sha256")
        proof = artifact.get("evidence")
        if proof is not None and (
            not isinstance(proof, dict) or proof.get("sha256") != digest
        ):
            raise ValueError(f"artifact {name} digest evidence mismatch")
        declarations[name] = {"declared_sha256": digest}
    return declarations


def build_evidence(
    output: Any, target: ToolTarget, attempt_id: str,
    transport_envelope: dict[str, Any],
) -> dict[str, Any]:
    return {
        "output_sha256": digest_json(output),
        "artifacts": artifact_declarations(output),
        "gateway": {
            "target": target.model_dump(mode="json"),
            "attempt_id": attempt_id,
            "transport_envelope_sha256": digest_json(transport_envelope),
        },
    }


def verify_artifacts(output: Any) -> dict[str, Any]:
    """Backward-compatible declaration-evidence helper."""
    return {"artifacts": artifact_declarations(output),
            "output_sha256": digest_json(output)}
