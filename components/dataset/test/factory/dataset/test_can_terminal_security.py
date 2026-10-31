"""Adversarial path and source-binding tests for the CAN terminal."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from factory.dataset.runtime.adapters.local_can_attempts import LocalCanAttemptStore
from factory.dataset.runtime.can_terminal_models import CanTerminalRequest
from factory.dataset.runtime.can_terminal_service import CanTerminalService

from .can_intelligence_fixtures import DBC_TEXT


class _Pipeline:
    def __init__(self, root: Path) -> None:
        self.root, self.calls = root, 0

    def run(self, request, canonical):
        self.calls += 1
        content = json.dumps({"request": canonical.request_sha256}).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = self.root / "can_terminal" / "fake" / f"bundle-{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {
            "status": "completed", "attempt_id": request.attempt_id,
            "request_sha256": canonical.request_sha256,
            "artifacts": {"bundle": {
                "uri": path.resolve().as_uri(), "sha256": digest,
                "evidence": {"sha256": digest},
            }}, "stage_receipts": {},
        }


def _fixture(root: Path, attempt: str = "attempt-1") -> CanTerminalRequest:
    source = root / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "capture.mf4").write_bytes(b"mf4")
    dbc = root / "vehicle.dbc"
    dbc.write_text(DBC_TEXT)
    return CanTerminalRequest(
        attempt_id=attempt, mf4_dir=str(source), dbc_path=str(dbc),
    )


def _service(root: Path, pipeline, store=None) -> CanTerminalService:
    return CanTerminalService(
        root, pipeline, store, verifier=lambda *args, **kwargs: None,
    )


def test_source_change_after_claim_fails_before_pipeline_effects(tmp_path: Path) -> None:
    request = _fixture(tmp_path)
    source = Path(request.mf4_dir) / "capture.mf4"

    class MutatingStore(LocalCanAttemptStore):
        def claim(self, attempt_id: str, request_sha256: str):
            result = super().claim(attempt_id, request_sha256)
            source.write_bytes(b"changed-after-hash")
            return result

    pipeline = _Pipeline(tmp_path)
    with pytest.raises(ValueError, match="source changed after request binding"):
        _service(tmp_path, pipeline, MutatingStore(tmp_path)).materialize(request)
    assert pipeline.calls == 0
    assert not list((tmp_path / "jobs").glob("*.json"))


def test_preexisting_terminal_symlink_cannot_escape_storage_root(tmp_path: Path) -> None:
    root, outside = tmp_path / "store", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "can_terminal").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="contains a symlink"):
        CanTerminalService(root)
    assert not list(outside.iterdir())


@pytest.mark.parametrize("attempt_id", ["../escape", "bad key", "x" * 129, "é"])
def test_attempt_id_is_bounded_safe_ascii(tmp_path: Path, attempt_id: str) -> None:
    with pytest.raises(ValueError, match="attempt_id"):
        _fixture(tmp_path, attempt=attempt_id)


@pytest.mark.parametrize("source_kind", ["mf4", "dbc", "context"])
def test_post_claim_source_symlink_swap_is_rejected(
    tmp_path: Path, source_kind: str,
) -> None:
    request = _fixture(tmp_path, attempt=f"swap-{source_kind}")
    context = tmp_path / "context.json"
    context.write_bytes(b"context")
    if source_kind == "context":
        request = request.model_copy(update={
            "use_context": True, "context_sources": (str(context),),
        })
    target = {
        "mf4": Path(request.mf4_dir) / "capture.mf4",
        "dbc": Path(request.dbc_path), "context": context,
    }[source_kind]
    outside = tmp_path / f"outside-{source_kind}{target.suffix}"
    outside.write_bytes(target.read_bytes())

    class SwappingStore(LocalCanAttemptStore):
        def claim(self, attempt_id: str, request_sha256: str):
            result = super().claim(attempt_id, request_sha256)
            target.unlink()
            target.symlink_to(outside)
            return result

    pipeline = _Pipeline(tmp_path)
    with pytest.raises((OSError, ValueError)):
        _service(tmp_path, pipeline, SwappingStore(tmp_path)).materialize(request)
    assert pipeline.calls == 0


def test_external_path_overrides_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot reference external paths"):
        CanTerminalRequest.model_validate({
            **_fixture(tmp_path).model_dump(),
            "config_overrides": {"ingest": {"dbc_path": "/tmp/other.dbc"}},
        })
