from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from factory.devtools.runtime.file_ops import list_dir, read_file
from factory.devtools.runtime.path_resolver import PathRefused, bind_project, resolve_path
from factory.devtools.runtime.search_ops import search


def _project(tmp_path: Path):
    root = tmp_path / "workspace" / "project"
    root.mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("print('hello')\n# evidence\n")
    return root, bind_project("tenant", "owner", "session", str(root), (tmp_path,))


def test_bind_requires_absolute_marked_allowed_project(tmp_path) -> None:
    root, binding = _project(tmp_path)
    assert binding.root == str(root.resolve())
    with pytest.raises(PathRefused):
        bind_project("t", "o", "s", "relative", (tmp_path,))
    outside = tmp_path.parent / "outside-project"
    outside.mkdir(exist_ok=True)
    (outside / ".git").mkdir(exist_ok=True)
    with pytest.raises(PathRefused):
        bind_project("t", "o", "s", str(outside), (tmp_path,))


def test_read_returns_hash_and_refuses_binary_sensitive_and_hardlink(tmp_path) -> None:
    root, binding = _project(tmp_path)
    result = read_file(binding, "src/main.py")
    raw = (root / "src" / "main.py").read_bytes()
    assert result.content == raw.decode()
    assert result.sha256 == hashlib.sha256(raw).hexdigest()
    (root / "src" / "binary.bin").write_bytes(b"a\x00b")
    with pytest.raises(PathRefused, match="binary"):
        read_file(binding, "src/binary.bin")
    (root / ".env").write_text("SECRET=value")
    with pytest.raises(PermissionError):
        read_file(binding, ".env")
    os.link(root / "src" / "main.py", root / "src" / "linked.py")
    with pytest.raises(PathRefused, match="identity"):
        read_file(binding, "src/linked.py")


def test_symlink_escape_is_refused_and_hidden_from_listing(tmp_path) -> None:
    root, binding = _project(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("private")
    (root / "escape").symlink_to(outside)
    with pytest.raises(PathRefused, match="escapes"):
        resolve_path(binding, "escape", expect="file")
    names = {entry.path for entry in list_dir(binding).entries}
    assert "escape" not in names
    assert ".git" not in names


def test_bounded_content_and_filename_search(tmp_path) -> None:
    _, binding = _project(tmp_path)
    content = search(binding, "evidence", glob="*.py")
    assert [(item.path, item.line) for item in content.matches] == [("src/main.py", 2)]
    files = search(binding, "", glob="*.py")
    assert [item.path for item in files.matches] == ["src/main.py"]


@given(parts=st.lists(
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=12),
    min_size=1, max_size=5,
))
def test_any_resolved_relative_path_stays_inside_project(parts) -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        root, binding = _project(Path(directory))
        target = root.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("safe")
        try:
            resolved = resolve_path(binding, "/".join(parts), expect="file")
        except (PathRefused, PermissionError):
            return
        resolved.relative_to(Path(binding.root))


@pytest.mark.parametrize("path", ["../outside", "src/../../outside", "/etc/passwd"])
def test_traversal_and_absolute_paths_are_refused(tmp_path, path) -> None:
    _, binding = _project(tmp_path)
    with pytest.raises((PathRefused, ValueError)):
        resolve_path(binding, path)
