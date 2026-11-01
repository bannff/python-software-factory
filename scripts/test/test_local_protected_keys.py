"""The launcher's local protected-content keys are minted once, safely, and stable."""
from __future__ import annotations

import base64
import importlib.util
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "local_protected_keys", Path(__file__).resolve().parents[1] / "local_protected_keys.py")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
INDEX, KEK, KeyFileError, exports = _MODULE.INDEX, _MODULE.KEK, _MODULE.KeyFileError, _MODULE.exports


def _values(lines: list[str]) -> dict[str, str]:
    return dict(line.removeprefix("export ").split("=", 1) for line in lines)


def test_mints_once_then_reuses_the_same_keys(tmp_path) -> None:
    path = tmp_path / "keys.json"
    first = exports(path, {})
    assert exports(path, {}) == first
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    values = _values(first)
    assert set(values) == {KEK, INDEX}
    assert all(len(base64.b64decode(v, validate=True)) == 32 for v in values.values())


def test_operator_supplied_keys_win_and_nothing_is_written(tmp_path) -> None:
    path = tmp_path / "keys.json"
    assert exports(path, {KEK: "operator-kek", INDEX: "operator-index"}) == []
    assert not path.exists()


def test_each_key_is_overridden_independently(tmp_path) -> None:
    out = _values(exports(tmp_path / "keys.json", {INDEX: "operator-index"}))
    assert set(out) == {KEK}


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o400])
def test_existing_file_with_loose_mode_is_refused(tmp_path, mode) -> None:
    path = tmp_path / "keys.json"
    exports(path, {})
    path.chmod(mode)
    with pytest.raises(KeyFileError, match="0600"):
        exports(path, {})


def test_symlinked_key_file_is_refused(tmp_path) -> None:
    real = tmp_path / "real.json"
    exports(real, {})
    link = tmp_path / "keys.json"
    link.symlink_to(real)
    with pytest.raises(KeyFileError):
        exports(link, {})


def test_corrupt_file_is_refused_not_replaced(tmp_path) -> None:
    path = tmp_path / "keys.json"
    path.write_text('{"FACTORY_PROT')
    path.chmod(0o600)
    with pytest.raises(KeyFileError, match="JSON"):
        exports(path, {})
    assert path.read_text() == '{"FACTORY_PROT'


def test_concurrent_first_launches_share_one_key_pair(tmp_path) -> None:
    script = Path(__file__).resolve().parents[1] / "local_protected_keys.py"
    path = tmp_path / "keys.json"
    env = {k: v for k, v in os.environ.items() if k not in (KEK, INDEX)}
    launchers = [
        subprocess.Popen([sys.executable, str(script), str(path)], env=env,
                         stdout=subprocess.PIPE, text=True)
        for _ in range(8)
    ]
    outputs = [launcher.communicate()[0] for launcher in launchers]
    assert all(launcher.returncode == 0 for launcher in launchers)
    assert len(set(outputs)) == 1 and KEK in outputs[0]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_cli_exits_nonzero_on_an_unsafe_file(tmp_path) -> None:
    script = Path(__file__).resolve().parents[1] / "local_protected_keys.py"
    path = tmp_path / "keys.json"
    exports(path, {})
    path.chmod(0o644)
    env = {k: v for k, v in os.environ.items() if k not in (KEK, INDEX)}
    done = subprocess.run([sys.executable, str(script), str(path)], env=env,
                          capture_output=True, text=True)
    assert done.returncode != 0 and "0600" in done.stderr and done.stdout == ""
