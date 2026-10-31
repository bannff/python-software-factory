from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from factory.devtools.runtime.file_ops import read_file
from factory.devtools.runtime.file_write_ops import EditConflict, create_file, edit_file
from factory.devtools.runtime.path_resolver import PathRefused, bind_project


def _binding(tmp_path: Path):
    root = tmp_path / "workspace" / "project"
    (root / "src").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
    return root, bind_project("tenant", "owner", "session", str(root), (tmp_path,))


def test_atomic_create_then_hash_fenced_edit(tmp_path) -> None:
    root, binding = _binding(tmp_path)
    created = create_file(binding, "src/new.py", "print('one')\n")
    assert created.created and (root / "src/new.py").read_text() == "print('one')\n"
    assert created.sha256 == hashlib.sha256(b"print('one')\n").hexdigest()
    observed = read_file(binding, "src/new.py")
    edited = edit_file(binding, "src/new.py", "print('two')\n", observed.sha256)
    assert not edited.created
    assert (root / "src/new.py").read_text() == "print('two')\n"


def test_stale_hash_never_overwrites_newer_content(tmp_path) -> None:
    root, binding = _binding(tmp_path)
    create_file(binding, "src/new.py", "first\n")
    stale = read_file(binding, "src/new.py").sha256
    (root / "src/new.py").write_text("newer\n")
    with pytest.raises(EditConflict, match="changed"):
        edit_file(binding, "src/new.py", "stale overwrite\n", stale)
    assert (root / "src/new.py").read_text() == "newer\n"


def test_create_refuses_existing_sensitive_and_symlink_targets(tmp_path) -> None:
    root, binding = _binding(tmp_path)
    create_file(binding, "src/new.py", "safe\n")
    with pytest.raises(FileExistsError):
        create_file(binding, "src/new.py", "overwrite\n")
    with pytest.raises(PermissionError):
        create_file(binding, ".env", "SECRET=value\n")
    outside = tmp_path / "outside.py"
    outside.write_text("outside\n")
    (root / "src/link.py").symlink_to(outside)
    with pytest.raises(PathRefused):
        edit_file(
            binding, "src/link.py", "bad\n",
            hashlib.sha256(b"outside\n").hexdigest(),
        )
    assert outside.read_text() == "outside\n"
