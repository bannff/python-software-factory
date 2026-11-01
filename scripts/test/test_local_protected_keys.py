"""The launcher's local protected-content keys are minted once and then stable."""
from __future__ import annotations

import base64
import stat

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "local_protected_keys", Path(__file__).resolve().parents[1] / "local_protected_keys.py")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
INDEX, KEK, exports = _MODULE.INDEX, _MODULE.KEK, _MODULE.exports


def test_mints_once_then_reuses_the_same_keys(tmp_path) -> None:
    path = tmp_path / "keys.json"
    first = exports(path, {})
    assert exports(path, {}) == first
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    values = dict(line.removeprefix("export ").split("=", 1) for line in first)
    assert set(values) == {KEK, INDEX}
    assert all(len(base64.b64decode(v, validate=True)) == 32 for v in values.values())


def test_operator_supplied_key_wins_and_nothing_is_written(tmp_path) -> None:
    path = tmp_path / "keys.json"
    assert exports(path, {KEK: "operator-key"}) == []
    assert not path.exists()
