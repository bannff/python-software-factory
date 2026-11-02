"""Guard: a bad find/replace of the product name must not reappear (#113).

"Companion X" / "companion-x" / "companion_x" were once replaced by the phrases
"the control-plane runtime" / "the control-plane project", corrupting skill
front matter, steering, recipes and docs ("the the control-plane runtime").
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORRUPTED = ("the control-plane runtime", "the control-plane project")
# Genuine "control-plane" prose (arcade bricks) and this guard's own literals.
ALLOWED_PREFIXES = (
    "components/arcade_config/",
    "bases/openarcade/",
    "scripts/test/test_rename_corruption_guard.py",
)


def tracked_text_files() -> list[Path]:
    if not (ROOT / ".git").exists():
        return []
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout.decode()
    return [
        ROOT / rel
        for rel in out.split("\0")
        if rel and not rel.startswith(ALLOWED_PREFIXES)
    ]


def corrupted_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    rel = path.relative_to(ROOT)
    return [
        f"{rel}:{n}: {line.strip()[:100]}"
        for n, line in enumerate(text.splitlines(), 1)
        if any(phrase in line for phrase in CORRUPTED)
    ]


def test_no_rename_corruption_in_tracked_files() -> None:
    files = tracked_text_files()
    if not files:
        pytest.skip("not a git checkout")
    hits = [hit for path in files for hit in corrupted_lines(path)]
    assert not hits, f"{len(hits)} corrupted lines (#113):\n" + "\n".join(hits[:40])


def test_behavior_skill_front_matter_uses_its_id() -> None:
    skill = ROOT / "components/agent/src/factory/agent/skills/companion-x-behavior/SKILL.md"
    if not skill.exists():
        pytest.skip("skill not present")
    assert "name: companion-x-behavior" in skill.read_text(encoding="utf-8").splitlines()
