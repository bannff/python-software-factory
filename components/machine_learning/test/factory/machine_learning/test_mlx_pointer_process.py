"""Process-boundary and namespace-swap tests for MLX pointer publication."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

import pytest

pytest.importorskip("mlx.core", reason="native MLX acceptance requires Apple Silicon")
pytest.importorskip("peft", reason="neural passport helpers require mlx-test")

from factory.machine_learning.runtime.adapters.mlx_artifact import persist_native_model
from factory.machine_learning.runtime.mlx_publication import (
    require_mlx_reference, verified_mlx_tree,
)

from .mlx_pointer_fixtures import PUBLISHER, mlx_pointer_case, model_args, objects


def test_pinned_handle_wins_swap_consume_restore(
    tmp_path: Path, mlx_pointer_case,
) -> None:
    reference = Path(mlx_pointer_case[1].model_artifact.uri.removeprefix("file://"))
    object_path = require_mlx_reference(reference)[0]
    original = (object_path / "factory_model.json").read_bytes()
    substitute = shutil.copytree(
        object_path, object_path.parent / ".substitute-test.mlx-object",
    )
    config = substitute / "factory_model.json"
    config.chmod(0o600)
    config.write_bytes(b"attacker-selected-bytes")
    from factory.machine_learning.runtime.passport_tree_seal import seal_read_only_tree
    seal_read_only_tree(substitute)
    parked = object_path.parent / ".parked-test.mlx-object"
    with pytest.raises(ValueError, match="MLX object changed while reading"):
        with verified_mlx_tree(reference) as tree:
            os.rename(object_path, parked)
            os.rename(substitute, object_path)
            try:
                assert tree.read_bytes("factory_model.json") == original
                assert (object_path / "factory_model.json").read_bytes() != original
            finally:
                os.rename(object_path, substitute)
                os.rename(parked, object_path)


def test_two_process_same_digest_selects_one_sealed_object(
    tmp_path: Path, mlx_pointer_case,
) -> None:
    root = tmp_path / "concurrent"
    root.mkdir()
    reference = Path(mlx_pointer_case[1].model_artifact.uri.removeprefix("file://"))
    ready_read, ready_write = os.pipe()
    start_read, start_write = os.pipe()
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", PUBLISHER, str(reference), str(root),
             str(ready_write), str(start_read)],
            pass_fds=(ready_write, start_read), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        for _ in range(2)
    ]
    os.close(ready_write); os.close(start_read)
    assert b"".join(os.read(ready_read, 1) for _ in range(2)) == b"rr"
    os.close(ready_read)
    os.write(start_write, b"go"); os.close(start_write)
    results = [process.communicate(timeout=120) for process in processes]
    assert all(process.returncode == 0 for process in processes), results
    references = [path for path in root.iterdir() if len(path.name) == 64]
    assert len(references) == 1
    selected = require_mlx_reference(references[0])[0]
    assert objects(root) == [selected]
    assert stat.S_IMODE(references[0].stat().st_mode) == 0o400
    assert stat.S_IMODE(selected.stat().st_mode) == 0o500


def test_exit_after_seal_retry_adopts_orphan(
    tmp_path: Path, mlx_pointer_case,
) -> None:
    root = tmp_path / "exit-orphan"
    root.mkdir()
    reference = Path(mlx_pointer_case[1].model_artifact.uri.removeprefix("file://"))
    crashed = subprocess.run(
        [sys.executable, "-c", PUBLISHER, str(reference), str(root)],
        capture_output=True, text=True,
        env={**os.environ, "MLX_TEST_CRASH": "after-seal"}, timeout=120,
    )
    assert crashed.returncode == 73, crashed.stderr
    orphan, = objects(root)
    assert not [path for path in root.iterdir() if len(path.name) == 64]
    published = persist_native_model(*model_args(mlx_pointer_case, root))
    assert require_mlx_reference(published)[0] == orphan
    assert objects(root) == [orphan]


@pytest.mark.parametrize(("mode", "code"), [
    ("before-rename", 74), ("after-rename", 75),
])
def test_pointer_publication_crash_boundary_recovers(
    tmp_path: Path, mlx_pointer_case, mode: str, code: int,
) -> None:
    root = tmp_path / mode
    root.mkdir()
    source = Path(mlx_pointer_case[1].model_artifact.uri.removeprefix("file://"))
    crashed = subprocess.run(
        [sys.executable, "-c", PUBLISHER, str(source), str(root)],
        capture_output=True, text=True,
        env={**os.environ, "MLX_TEST_CRASH": mode}, timeout=120,
    )
    assert crashed.returncode == code, crashed.stderr
    published = persist_native_model(*model_args(mlx_pointer_case, root))
    selected = require_mlx_reference(published)[0]
    assert objects(root) == [selected]
    assert not list(root.glob(".*.tmp"))
    assert stat.S_IMODE(published.stat().st_mode) == 0o400
    assert stat.S_IMODE(selected.stat().st_mode) == 0o500
