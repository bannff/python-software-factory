"""Behavioral boundaries for the sibling sealed routing image."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).parents[1] / "experiments/edge_models/edge-routing-sdk-001"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sources(tmp_path: Path, builder):
    result = {}
    for name in builder.SOURCE_FILES:
        path = tmp_path / "reviewed" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name in {
            "edge_models/edge-mesh-coordinator-001/records.py",
            "edge_models/edge-mesh-coordinator-001/reducer.py",
        }:
            path.write_bytes((HERE.parents[1] / name).read_bytes())
        else:
            path.write_bytes(f"reviewed {name}\n".encode())
        result[name] = path
    sdk = "a" * 64
    scenario = {"sdk_distribution_sha256": sdk}
    for key, name in (("model_sha256", "model.json"), ("cohort_sha256", "cohort.json"),
                      ("source_event_sha256", "source-event.json"), ("policy_sha256", "policy.json")):
        scenario[key] = builder.sha256(result[name])
    result["scenario.json"].write_text(json.dumps(scenario))
    pins = {
        "schema_version": 2,
        "sdk_distribution_sha256": sdk,
        "entrypoint_sha256": builder.sha256(HERE / "sealed_entrypoint.py"),
        "files": {name: builder.sha256(path) for name, path in result.items()},
        "dependencies": {
            "lock_sha256": builder.sha256(HERE / builder.DEPENDENCY_LOCK_NAME),
            "wheels": builder.WHEEL_FILES.copy(),
        },
    }
    return result, pins


def test_context_preserves_sibling_layout_and_is_exact(tmp_path: Path):
    builder = load("sealed_image")
    paths, pins = sources(tmp_path, builder)
    context = tmp_path / "context"
    builder.assemble_context(context, paths, pins, HERE / "sealed_entrypoint.py", builder.BASE_TAG)
    assert {p.relative_to(context).as_posix() for p in context.rglob("*") if p.is_file()} == builder.CONTEXT_FILES
    assert (context / "edge_models/edge-mesh-coordinator-001/records.py").is_file()
    assert (context / "edge_models/edge-routing-sdk-001/attestation.py").is_file()
    dockerfile = (context / "Dockerfile").read_text()
    assert "COPY ." not in dockerfile
    assert "--no-index" in dockerfile
    assert "--require-hashes" in dockerfile
    assert (context / builder.DEPENDENCY_LOCK_NAME).is_file()
    assert (context / builder.WHEELHOUSE_NAME / next(iter(builder.WHEEL_FILES))).is_file()
    assert 'ENTRYPOINT ["/usr/local/bin/python", "/sealed/entrypoint.py"]' in dockerfile
    assert 'CMD ["preflight"]' in dockerfile
    (context / "license.txt").write_text("secret")
    with pytest.raises(ValueError, match="extra"):
        builder.validate_context(context)
    (context / "license.txt").unlink()
    (context / "unreviewed").mkdir()
    with pytest.raises(ValueError, match="extra"):
        builder.validate_context(context)


def test_missing_or_drifted_source_stops_before_docker(tmp_path: Path, monkeypatch):
    builder = load("sealed_image")
    paths, pins = sources(tmp_path, builder)
    pins_file = tmp_path / "pins.json"
    pins_file.write_text(json.dumps(pins))
    monkeypatch.setattr(builder, "docker", lambda *args, **kwargs: pytest.fail("Docker invoked"))
    paths["edge_models/edge-routing-sdk-001/run.py"].write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        builder.build(paths, pins_file, tmp_path / "build", tmp_path / "profile.yaml")
    assert not (tmp_path / "build").exists()
    paths["edge_models/edge-routing-sdk-001/run.py"].unlink()
    with pytest.raises(ValueError, match="missing"):
        builder.build(paths, pins_file, tmp_path / "build", tmp_path / "profile.yaml")


def test_visual_model_source_is_required_and_pinned(tmp_path: Path):
    builder = load("sealed_image")
    visual = "edge_models/edge-visual-quality-mesh-001/model.py"
    assert visual in builder.SOURCE_FILES
    paths, pins = sources(tmp_path, builder)
    context = tmp_path / "context"
    paths[visual].write_text("unreviewed change")
    with pytest.raises(ValueError, match="hash mismatch"):
        builder.assemble_context(context, paths, pins, HERE / "sealed_entrypoint.py", builder.BASE_TAG)
    assert not context.exists()
    paths[visual].unlink()
    with pytest.raises(ValueError, match="missing"):
        builder.assemble_context(context, paths, pins, HERE / "sealed_entrypoint.py", builder.BASE_TAG)
    assert not context.exists()


def test_entrypoint_rejects_args_and_requires_secret_only_for_run(tmp_path: Path, monkeypatch, capsys):
    builder = load("sealed_image")
    entrypoint = load("sealed_entrypoint")
    paths, pins = sources(tmp_path, builder)
    builder.assemble_context(tmp_path / "context", paths, pins, HERE / "sealed_entrypoint.py", builder.BASE_TAG)
    root = tmp_path / "context"
    monkeypatch.setattr(entrypoint, "observed_sdk_digest", lambda: "a" * 64)
    monkeypatch.setattr(entrypoint, "validate_pydantic_contract",
                        lambda root: entrypoint.DEPENDENCY_VERSIONS.copy())
    monkeypatch.setattr(entrypoint, "LICENSE", tmp_path / "missing-secret")
    assert entrypoint.main(["preflight"], root=root) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["license_used"] is False
    assert result["pydantic_versions"] == entrypoint.DEPENDENCY_VERSIONS
    monkeypatch.setenv("EDGE_ROUTING_IMAGE_SHA256", "b" * 64)
    assert entrypoint.main(["run"], root=root) == 2
    assert json.loads(capsys.readouterr().out)["error_type"] == "ValueError"
    assert entrypoint.main(["run", "--scenario", "other"]) == 2
    assert entrypoint.main([]) == 2


def test_profile_matches_collector_identity(tmp_path: Path):
    builder = load("sealed_image")
    path = tmp_path / "profile.yaml"
    image_id = "sha256:" + "b" * 64
    builder.write_profile(path, image_id)
    profile = yaml.safe_load(path.read_text())
    assert profile["image"] == image_id
    assert profile["container_name"] == "edge-routing-sdk"
    assert profile["entrypoint"] == ["run"]
    assert profile["env_vars"]["EDGE_ROUTING_IMAGE_SHA256"] == "b" * 64
    assert profile["secret_refs"] == ["ditto-offline-license"]
    assert profile["peer_network"]["network_id"] == "edge-routing-sdk-lab"
    assert profile["peer_network"]["alias"] == "edge-routing-sdk"
    assert profile["peer_network"]["internal"] is True
    assert profile["replace_existing"] is False
    assert profile.get("ports", {}) == {}


def test_build_preflights_without_license_before_writing_profile(tmp_path: Path, monkeypatch):
    builder = load("sealed_image")
    paths, pins = sources(tmp_path, builder)
    pins_file = tmp_path / "reviewed-pins.json"
    pins_file.write_text(json.dumps(pins))
    base_id = "sha256:" + "b" * 64
    final_id = "sha256:" + "c" * 64
    monkeypatch.setattr(builder, "inspect_image", lambda ref: (
        (final_id if ref == final_id else base_id), "linux/arm64"))
    invoked = []

    def docker(*args):
        invoked.append(args)
        if args[0] == "build":
            Path(args[args.index("--iidfile") + 1]).write_text(final_id)
            return ""
        assert args[0] == "run"
        assert "--network" in args and args[args.index("--network") + 1] == "none"
        assert "--read-only" in args
        assert all("secret" not in item and "license" not in item for item in args)
        return json.dumps({"status": "passed", "sdk_distribution_sha256": "a" * 64,
                           "pydantic_versions": builder.DEPENDENCY_VERSIONS,
                           "license_used": False, "peers_launched": False})

    monkeypatch.setattr(builder, "docker", docker)
    output = tmp_path / "build"
    profile_path = tmp_path / "profile.yaml"
    evidence = builder.build(paths, pins_file, output, profile_path)
    assert [args[0] for args in invoked] == ["build", "run"]
    assert evidence["final_image_id"] == final_id
    assert evidence["license_mounted"] is False
    assert profile_path.exists()


def test_entrypoint_and_scenario_pins_fail_closed(tmp_path: Path, monkeypatch):
    builder = load("sealed_image")
    entrypoint = load("sealed_entrypoint")
    paths, pins = sources(tmp_path, builder)
    root = tmp_path / "context"
    builder.assemble_context(root, paths, pins, HERE / "sealed_entrypoint.py", builder.BASE_TAG)
    monkeypatch.setattr(entrypoint, "observed_sdk_digest", lambda: "a" * 64)
    monkeypatch.setattr(entrypoint, "validate_pydantic_contract",
                        lambda root: entrypoint.DEPENDENCY_VERSIONS.copy())
    (root / "entrypoint.py").write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        entrypoint.preflight(root)
    (root / "entrypoint.py").write_bytes((HERE / "sealed_entrypoint.py").read_bytes())
    (root / "scenario.json").write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        entrypoint.preflight(root)


def test_dependency_wheelhouse_rejects_missing_extra_tampered_and_wrong_platform(tmp_path: Path):
    builder = load("sealed_image")
    _, pins = sources(tmp_path, builder)
    original = HERE / builder.WHEELHOUSE_NAME
    for case in ("missing", "extra", "tampered", "wrong-platform"):
        wheelhouse = tmp_path / case
        wheelhouse.mkdir()
        for source in original.iterdir():
            (wheelhouse / source.name).write_bytes(source.read_bytes())
        if case == "missing":
            (wheelhouse / next(iter(builder.WHEEL_FILES))).unlink()
            expected = "missing or extra"
        elif case == "extra":
            (wheelhouse / "unreviewed.whl").write_bytes(b"unexpected")
            expected = "missing or extra"
        elif case == "tampered":
            target = wheelhouse / next(iter(builder.WHEEL_FILES))
            target.write_bytes(target.read_bytes() + b"tampered")
            expected = "hash mismatch"
        else:
            core = next(name for name in builder.WHEEL_FILES if name.startswith("pydantic_core-"))
            (wheelhouse / core).rename(wheelhouse / core.replace("aarch64", "x86_64"))
            expected = "missing or extra"
        with pytest.raises(ValueError, match=expected):
            builder.validate_wheelhouse(HERE / builder.DEPENDENCY_LOCK_NAME, wheelhouse, pins)


def test_dependency_lock_rejects_platform_or_pin_drift(tmp_path: Path):
    builder = load("sealed_image")
    _, pins = sources(tmp_path, builder)
    lock = tmp_path / "wrong-platform.lock"
    lock.write_text((HERE / builder.DEPENDENCY_LOCK_NAME).read_text().replace(
        "f26a1032bcce6ca4b4670eb3f7d8195bd0a8b8f255f1307823e217ca3cfa7c27",
        "3a5a06d8ed01dad5575056b5187e5959b336793c6047920a3441ee5b03533836"))
    pins["dependencies"]["lock_sha256"] = builder.sha256(lock)
    with pytest.raises(ValueError, match="unpinned distributions"):
        builder.validate_wheelhouse(lock, HERE / builder.WHEELHOUSE_NAME, pins)


def test_preflight_imports_source_pinned_records_and_reducer(tmp_path: Path, monkeypatch):
    builder = load("sealed_image")
    entrypoint = load("sealed_entrypoint")
    paths, pins = sources(tmp_path, builder)
    context = tmp_path / "context"
    builder.assemble_context(context, paths, pins, HERE / "sealed_entrypoint.py", builder.BASE_TAG)
    monkeypatch.setattr(entrypoint, "observed_sdk_digest", lambda: "a" * 64)
    result = entrypoint.preflight(context)
    assert result["status"] == "passed"
    assert result["pydantic_versions"] == entrypoint.DEPENDENCY_VERSIONS
