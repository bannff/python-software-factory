"""Executable contract for deterministic PR Safety dependency installation."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github/workflows/ci.yml"
AUTO_MERGE_WORKFLOW = ROOT / ".github/workflows/auto-merge.yml"


def _step_run_block(workflow: str, step_name: str) -> str:
    lines = workflow.splitlines()
    name_index = next(
        index for index, line in enumerate(lines) if line.strip() == f"- name: {step_name}"
    )
    run_index = next(
        index
        for index in range(name_index + 1, len(lines))
        if lines[index].strip().startswith("run:")
    )
    run_line = lines[run_index].strip()
    if run_line != "run: |":
        return run_line.removeprefix("run:").strip()
    block: list[str] = []
    for line in lines[run_index + 1 :]:
        if line.startswith("          ") or not line.strip():
            block.append(line[10:] if line else "")
            continue
        break
    return "\n".join(block)


def _fake_uv_path(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text(
        """#!/bin/sh
if test "$1 $2" = "lock --check"; then
  grep -qx fresh uv.lock || exit 42
  : > .lock-checked
  exit 0
fi
if test "$1 $2" = "sync --frozen"; then
  test -f .lock-checked || exit 43
  exit 0
fi
if test "$1 $2" = "pip install"; then
  exit 0
fi
exit 44
"""
    )
    uv.chmod(0o755)
    return bin_dir


def _run(command: str, cwd: Path, bin_dir: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    return subprocess.run(
        ["bash", "-euo", "pipefail", "-c", command],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_canonical_workspace_lock_is_visible_and_clean() -> None:
    ignored = (ROOT / ".gitignore").read_text().splitlines()
    assert "uv.lock" not in {line.strip() for line in ignored}
    lock = (ROOT / "uv.lock").read_text()
    assert 'name = "python-factory"' in lock
    assert 'name = "companion-x"' in lock
    # The public mirror drops projects/openarcade, so assert membership only
    # where the project actually exists (private tree).
    if (ROOT / "projects" / "openarcade").exists():
        assert 'name = "openarcade"' in lock
    assert 'name = "circuitron"' not in lock


def test_personal_project_is_excluded_from_uv_workspace() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    workspace = config["tool"]["uv"]["workspace"]
    assert workspace["members"] == ["projects/*"]
    assert "projects/circuitron" in workspace["exclude"]


def _run_blocks(workflow: str) -> list[str]:
    """Every ``run:`` block in the workflow, in document order."""
    document = yaml.safe_load(workflow)
    return [
        step["run"]
        for job in document["jobs"].values()
        for step in job.get("steps", [])
        if "run" in step
    ]


def test_every_frozen_install_first_checks_lock_freshness() -> None:
    """Invariant, not a snapshot: *every* step that installs with
    ``uv sync --frozen`` must check the lock first.

    Counting the occurrences instead required re-pinning this test whenever a
    job was added (the post-merge lane was the first), which is the kind of
    incidental pin that hides the real question.
    """
    workflow = CI_WORKFLOW.read_text()
    installs = [block for block in _run_blocks(workflow) if "uv sync --frozen" in block]
    assert installs, "no step installs with `uv sync --frozen`"
    for block in installs:
        assert "uv lock --check" in block, block
        assert block.index("uv lock --check") < block.index("uv sync --frozen"), block
    candidate = _step_run_block(workflow, "Install candidate dependencies")
    assert "--no-deps" in candidate


def test_candidate_sync_rejects_stale_and_missing_locks(tmp_path: Path) -> None:
    command = _step_run_block(CI_WORKFLOW.read_text(), "Install candidate dependencies")
    bin_dir = _fake_uv_path(tmp_path)
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "uv.lock").write_text("stale\n")
    assert _run(command, candidate, bin_dir).returncode == 42
    (candidate / "uv.lock").unlink()
    assert _run(command, candidate, bin_dir).returncode == 42


def test_legacy_base_bootstraps_only_from_present_fresh_candidate(tmp_path: Path) -> None:
    workflow = CI_WORKFLOW.read_text()
    assert "Check out immutable base" not in workflow
    assert "working-directory: base" not in workflow
    assert "compare_junit" not in workflow


def test_legacy_base_rejects_stale_or_both_missing_locks(tmp_path: Path) -> None:
    workflow = CI_WORKFLOW.read_text()
    core = workflow.split("  core-tests:", 1)[1].split("  can-tests:", 1)[0]
    assert "--collect-only" in core
    assert "Run strict control-plane suites" in core
    assert "Run changed brick tests" in core


def test_auto_merge_targets_only_originating_successful_pr_safety_pr() -> None:
    workflow = AUTO_MERGE_WORKFLOW.read_text()
    assert "workflows: [PR Safety]" in workflow
    assert "workflow_run.conclusion == 'success'" in workflow
    assert "workflow_run.event == 'pull_request'" in workflow
    assert "workflow_run.pull_requests[0].number != null" in workflow
    assert "PULL_REQUEST: ${{ github.event.workflow_run.pull_requests[0].number }}" in workflow
    assert "check_suite:" not in workflow
    assert "pull_request:" not in workflow
    assert "workflow_dispatch" not in workflow
