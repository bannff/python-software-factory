"""Pure flat MCP payload construction for CAN keystone Dataset stages."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


def uri_to_path(uri: str) -> Path | None:
    """Resolve file URIs to local paths; return None for other schemes."""
    if not uri.startswith("file://") and not uri.startswith("file:/"):
        return None
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    raw = unquote(parsed.path) if parsed.path else uri[len(parsed.scheme) + 1:]
    return Path(raw).resolve()


def digest(content: bytes) -> str:
    """Return a SHA-256 hex digest."""
    return hashlib.sha256(content).hexdigest()


def write_snapshot(dir_: Path, label: str, payload: dict | bytes) -> dict[str, str]:
    """Write an immutable content-addressed snapshot and return flat fields."""
    dir_.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() \
        if isinstance(payload, dict) else payload
    content_digest = digest(content)
    path = dir_ / f"{label}-{content_digest}.json"
    if not path.exists():
        path.write_bytes(content)
    return {"uri": path.resolve().as_uri(), "digest": content_digest}


def _stage_name(recipe_uri: str) -> str:
    prefix = "recipe://local/"
    if not recipe_uri.startswith(prefix) or "@" not in recipe_uri:
        raise ValueError(f"Unsupported Dataset recipe URI: {recipe_uri}")
    if recipe_uri == "recipe://local/can-window@2":
        return "can_window_v2"
    return recipe_uri.removeprefix(prefix).split("@", 1)[0].replace("-", "_")


def build_dataset_request(
    recipe_uri: str,
    input_uris: list[str],
    context_config: dict[str, Any],
    snapshots_dir: Path,
    idempotency_key: str,
    input_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Build the flat arguments accepted by ``dataset_submit_generation``."""
    if input_roles is not None and len(input_roles) != len(input_uris):
        raise ValueError("input_uris and input_roles must have equal lengths")
    artifact_uris: list[str] = []
    artifact_digests: list[str] = []
    for uri in input_uris:
        path = uri_to_path(uri) or Path(uri)
        artifact_uris.append(path.resolve().as_uri())
        artifact_digests.append(
            digest(path.read_bytes()) if path.exists() else digest(uri.encode())
        )
    stage_name = _stage_name(recipe_uri)
    context = write_snapshot(snapshots_dir, "context", {
        "stage_overrides": {stage_name: context_config},
    })
    tool_schema = write_snapshot(
        snapshots_dir, "tool-schema", b'{"allowed_tools":[]}',
    )
    return {
        "recipe_uri": recipe_uri,
        "recipe_digest": digest(recipe_uri.encode()),
        "context_snapshot_uri": context["uri"],
        "context_snapshot_digest": context["digest"],
        "tool_schema_snapshot_uri": tool_schema["uri"],
        "tool_schema_snapshot_digest": tool_schema["digest"],
        "allowed_tools": [],
        "input_artifact_uris": artifact_uris,
        "input_artifact_digests": artifact_digests,
        "input_artifact_roles": input_roles,
        "fail_closed": True,
        "retry_from_checkpoint_only": True,
        "idempotency_key": idempotency_key,
        "schema_version": "1.0",
    }


__all__ = ["build_dataset_request", "digest", "uri_to_path", "write_snapshot"]
