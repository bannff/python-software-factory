"""Properties for Dataset CAN terminal create-or-match durability."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from hypothesis import given, settings, strategies as st
import pytest

from factory.dataset.runtime.can_terminal_models import CanTerminalRequest
from factory.dataset.runtime.can_terminal_service import CanTerminalService

from .can_intelligence_fixtures import DBC_TEXT, write_catalog, write_probe_mf4


class _Pipeline:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def run(self, request, canonical):
        self.calls += 1
        content = json.dumps(
            {"request": canonical.request_sha256}, sort_keys=True,
            separators=(",", ":"),
        ).encode()
        digest = hashlib.sha256(content).hexdigest()
        path = self.root / "can_terminal" / "fake" / f"bundle-{digest}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {
            "schema_version": "1.0", "status": "completed",
            "attempt_id": request.attempt_id,
            "request_sha256": canonical.request_sha256,
            "artifacts": {"bundle": {
                "uri": path.resolve().as_uri(), "sha256": digest,
                "evidence": {"sha256": digest},
            }},
            "stage_receipts": {},
        }


def _verify_fake(root: Path, terminal: dict, **_kwargs) -> None:
    if terminal.get("status") != "completed":
        return
    for artifact in terminal["artifacts"].values():
        path = Path(artifact["uri"].removeprefix("file://"))
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError("CAN terminal artifact digest mismatch")


def _service(root: Path, pipeline, store=None) -> CanTerminalService:
    return CanTerminalService(root, pipeline, store, verifier=_verify_fake)


def _fixture(root: Path, attempt: str = "attempt-1", vehicle: str = "v1"):
    source = root / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "capture.mf4").write_bytes(b"mf4")
    dbc = root / "vehicle.dbc"
    dbc.write_text(DBC_TEXT)
    return CanTerminalRequest(
        attempt_id=attempt, mf4_dir=str(source), dbc_path=str(dbc),
        vehicle_id=vehicle,
    )


def _bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def test_equal_retry_and_fresh_runtime_replay_exact_terminal(tmp_path: Path) -> None:
    request = _fixture(tmp_path)
    first_pipeline = _Pipeline(tmp_path)
    first = _service(tmp_path, first_pipeline).materialize(request)
    second = _service(tmp_path, first_pipeline).materialize(request)
    restarted_pipeline = _Pipeline(tmp_path)
    restarted = _service(tmp_path, restarted_pipeline).materialize(request)
    assert first_pipeline.calls == 1
    assert restarted_pipeline.calls == 0
    assert _bytes(first) == _bytes(second) == _bytes(restarted)


def test_concurrent_equal_retries_run_effects_once(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    request = _fixture(tmp_path)
    pipeline = _Pipeline(tmp_path)
    services = [_service(tmp_path, pipeline) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda service: service.materialize(request), services))
    assert pipeline.calls == 1
    assert _bytes(results[0]) == _bytes(results[1])


def test_divergent_retry_conflicts_without_effects(tmp_path: Path) -> None:
    pipeline = _Pipeline(tmp_path)
    service = _service(tmp_path, pipeline)
    first = service.materialize(_fixture(tmp_path, vehicle="one"))
    before = {path.relative_to(tmp_path): path.read_bytes()
              for path in tmp_path.rglob("*") if path.is_file()}
    conflict = service.materialize(_fixture(tmp_path, vehicle="two"))
    after = {path.relative_to(tmp_path): path.read_bytes()
             for path in tmp_path.rglob("*") if path.is_file()}
    assert first["status"] == "completed"
    assert conflict["status"] == "conflict"
    assert pipeline.calls == 1
    assert before == after


def test_artifact_tamper_fails_closed_without_rerun(tmp_path: Path) -> None:
    request = _fixture(tmp_path)
    pipeline = _Pipeline(tmp_path)
    first = _service(tmp_path, pipeline).materialize(request)
    Path(first["artifacts"]["bundle"]["uri"].removeprefix("file://")).write_bytes(b"tamper")
    with pytest.raises(ValueError, match="artifact digest mismatch"):
        _service(tmp_path, pipeline).materialize(request)
    assert pipeline.calls == 1


def test_attempt_record_tamper_fails_closed_without_rerun(tmp_path: Path) -> None:
    request = _fixture(tmp_path)
    pipeline = _Pipeline(tmp_path)
    _service(tmp_path, pipeline).materialize(request)
    record = next((tmp_path / "can_terminal" / "attempts").glob("*.json"))
    value = json.loads(record.read_bytes())
    value["request_sha256"] = "f" * 64
    record.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="attempt record digest mismatch"):
        _service(tmp_path, pipeline).materialize(request)
    assert pipeline.calls == 1


def test_context_sources_are_ignored_when_context_is_disabled(tmp_path: Path) -> None:
    from factory.dataset.runtime.can_terminal_canonical import canonicalize_request
    plain = _fixture(tmp_path)
    ignored = plain.model_copy(update={"context_sources": ("/missing/context.json",)})
    assert canonicalize_request(plain).request_sha256 == canonicalize_request(ignored).request_sha256


@settings(max_examples=25, deadline=None)
@given(
    attempt=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-",
        min_size=1, max_size=20,
    ).filter(lambda value: value[0].isalnum()),
    first=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=1, max_size=20,
    ),
    second=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=1, max_size=20,
    ),
)
def test_retry_or_conflict_property(attempt: str, first: str, second: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pipeline = _Pipeline(root)
        service = _service(root, pipeline)
        original = service.materialize(_fixture(root, attempt, first))
        observed = service.materialize(_fixture(root, attempt, second))
        if first == second:
            assert _bytes(observed) == _bytes(original)
        else:
            assert observed["status"] == "conflict"
        assert pipeline.calls == 1


def test_catalog_resolves_terminal_without_explicit_dbc_path(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    write_probe_mf4(source)
    write_catalog(tmp_path)
    request = CanTerminalRequest(
        attempt_id="catalog-attempt", mf4_dir=str(source),
        vehicle_id="fixture-car", vehicle_alias="fixture-car",
    )
    pipeline = _Pipeline(tmp_path)
    result = _service(tmp_path, pipeline).materialize(request)
    assert result["status"] == "completed"
    assert pipeline.calls == 1
