"""Immutable definition artifact integrity, bounds, and MCP contracts."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlsplit

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from hypothesis import HealthCheck, given, settings, strategies as st
import pytest
from pydantic import ValidationError

from factory.dataset.interface import (
    DefinitionArtifact, dataset_publish_definition_artifact,
    dataset_resolve_definition_artifact,
)
from factory.dataset.mcp import definitions
from factory.dataset.runtime.definition_codec import (
    canonical_definition_bytes, parse_definition_json,
)
from factory.dataset.runtime.definition_models import DefinitionArtifactIntegrityError


def _artifact(content: dict | None = None) -> DefinitionArtifact:
    return DefinitionArtifact(
        schema_name="agent.execution-manifest", schema_version="1.0",
        identity="graph-alpha", version="7", content=content or {"nodes": []},
    )


def _path(uri: str) -> Path:
    return Path(unquote(urlsplit(uri).path))


def _tool(mcp: ToolCatalog, name: str):
    return asyncio.run(mcp.get_tool(name)).fn


@given(st.dictionaries(
    st.from_regex(r"[a-z][a-z0-9_]{0,8}", fullmatch=True),
    st.integers(min_value=-(2**31), max_value=2**31 - 1), max_size=8,
))
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_equal_replay_is_stable_for_canonical_json(
    tmp_path: Path, content: dict[str, int],
) -> None:
    artifact = _artifact(content)
    with TemporaryDirectory(dir=tmp_path) as directory:
        case_root = Path(directory)
        first = dataset_publish_definition_artifact(artifact, case_root, 4096)
        second = dataset_publish_definition_artifact(artifact, case_root, 4096)
        assert first.status == "published"
        assert second.status == "existing"
        assert second.ref == first.ref
        assert dataset_resolve_definition_artifact(
            first.ref, case_root, 4096,
        ) == artifact


def test_divergent_content_for_same_identity_version_conflicts(tmp_path: Path) -> None:
    first = dataset_publish_definition_artifact(_artifact({"value": 1}), tmp_path)
    conflict = dataset_publish_definition_artifact(_artifact({"value": 2}), tmp_path)
    assert conflict.status == "conflict"
    assert conflict.ref is None
    assert conflict.conflict.existing_digest == first.ref.digest
    assert conflict.conflict.requested_digest != first.ref.digest


def test_successful_round_trip_uses_canonical_bytes_and_sha256(tmp_path: Path) -> None:
    artifact = _artifact({"z": 1, "a": [True, None, "µ"]})
    published = dataset_publish_definition_artifact(artifact, tmp_path)
    assert published.ref is not None
    raw = _path(published.ref.uri).read_bytes()
    assert raw == canonical_definition_bytes(artifact)
    assert b'": ' not in raw and b", " not in raw
    assert len(raw) == published.ref.size_bytes
    assert dataset_resolve_definition_artifact(published.ref, tmp_path) == artifact


def test_digest_tamper_is_rejected(tmp_path: Path) -> None:
    published = dataset_publish_definition_artifact(_artifact({"value": 1}), tmp_path)
    path = _path(published.ref.uri)
    path.chmod(0o644)
    path.write_bytes(path.read_bytes().replace(b'"value":1', b'"value":2'))
    with pytest.raises(DefinitionArtifactIntegrityError, match="digest"):
        dataset_resolve_definition_artifact(published.ref, tmp_path)


@pytest.mark.parametrize("kind", ["traversal", "absolute"])
def test_traversal_and_absolute_escape_are_rejected(tmp_path: Path, kind: str) -> None:
    published = dataset_publish_definition_artifact(_artifact(), tmp_path)
    ref = published.ref
    if kind == "traversal":
        uri = f"file://{_path(ref.uri).parent}/../escape.json"
    else:
        uri = (tmp_path / "outside.json").as_uri()
    with pytest.raises(DefinitionArtifactIntegrityError, match="URI"):
        dataset_resolve_definition_artifact(ref.model_copy(update={"uri": uri}), tmp_path)


def test_any_symlink_in_resolve_path_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "store"
    published = dataset_publish_definition_artifact(_artifact(), root)
    definitions = root / "definition_artifacts"
    actual = tmp_path / "actual-definitions"
    definitions.rename(actual)
    definitions.symlink_to(actual, target_is_directory=True)
    with pytest.raises(DefinitionArtifactIntegrityError, match="symlink"):
        dataset_resolve_definition_artifact(published.ref, root)


def test_oversized_publish_rejects_before_parse_and_on_model_publish(tmp_path: Path) -> None:
    mcp = ToolCatalog("bounded-definitions")
    definitions.register(mcp, tmp_path, max_size_bytes=128)
    publish = _tool(mcp, "dataset_publish_definition_artifact")
    oversized = "{" + (" " * 256)
    with pytest.raises(ValueError, match="before parse"):
        parse_definition_json(oversized, 128)
    assert publish({"artifact_json": oversized}).ok is False
    with pytest.raises(ValueError, match="on publish"):
        dataset_publish_definition_artifact(
            _artifact({"payload": "x" * 256}), tmp_path, max_size_bytes=128,
        )


def test_oversized_resolve_fails_before_first_file_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    published = dataset_publish_definition_artifact(
        _artifact({"payload": "x" * 256}), tmp_path, max_size_bytes=4096,
    )
    import factory.dataset.runtime.atomic_io as atomic_io
    monkeypatch.setattr(
        atomic_io.os, "read",
        lambda *_: (_ for _ in ()).throw(AssertionError("read occurred")),
    )
    with pytest.raises(DefinitionArtifactIntegrityError, match="bounded"):
        dataset_resolve_definition_artifact(
            published.ref, tmp_path, max_size_bytes=128,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_name", "other"), ("schema_version", "2.0"),
     ("identity", "graph-beta"), ("version", "8")],
)
def test_schema_and_logical_version_mismatch_fail_closed(
    tmp_path: Path, field: str, value: str,
) -> None:
    published = dataset_publish_definition_artifact(_artifact(), tmp_path)
    with pytest.raises(DefinitionArtifactIntegrityError, match="mismatch|rooted"):
        dataset_resolve_definition_artifact(
            published.ref.model_copy(update={field: value}), tmp_path,
        )


def test_schema_name_and_version_are_required() -> None:
    payload = _artifact().model_dump(mode="json")
    for field in ("schema_name", "schema_version"):
        invalid = dict(payload)
        invalid.pop(field)
        with pytest.raises(ValidationError):
            DefinitionArtifact.model_validate(invalid)


def test_flat_mcp_contracts_round_trip_and_are_categorized(tmp_path: Path) -> None:
    mcp = ToolCatalog("definition-contracts")
    definitions.register(mcp, tmp_path, max_size_bytes=4096)
    publish = _tool(mcp, "dataset_publish_definition_artifact")
    resolve = _tool(mcp, "dataset_resolve_definition_artifact")
    result = publish({"artifact_json": json.dumps(
        _artifact().model_dump(mode="json"), indent=2,
    )})
    resolved = resolve(result.data.ref.model_dump(mode="json"))
    assert resolved.data.content == {"nodes": []}
    assert getattr(publish, "_mcp_category") == "operational"
    assert getattr(resolve, "_mcp_category") == "deterministic"
