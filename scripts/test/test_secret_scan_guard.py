"""CI core-test guard: no license-token material in committed evidence files.

Scans the tracked edge_models experiment tree (results.md, run-index.json,
build-evidence, telemetry JSONLs — anything git tracks) for the Ditto license
token pattern and UUID-format credentials in secret-bearing key contexts.

The scanner itself lives in scripts/hooks/secret_scan.py so the pre-commit
hook and the demo-driver scrub share one source of truth. To test detection
against the real token family, set SECRET_SCAN_TOKEN_PREFIXES to a comma-
separated list of >=8-char prefixes; CI runs pattern-only.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EDGE_MODELS = ROOT / "projects/companion_x/experiments/edge_models"

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
from secret_scan import LICENSE_TOKEN_PREFIX, find_hits, scan_file  # noqa: E402


def tracked_edge_model_files() -> list[Path]:
    if not (ROOT / ".git").exists() or not EDGE_MODELS.exists():
        return []
    result = subprocess.run(
        ["git", "ls-files", "projects/companion_x/experiments/edge_models/"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def test_scanner_flags_license_token_prefix() -> None:
    hits = find_hits("some line\nlicense = o2d1c2VyX3Rlc3R0b2tlbmV4cGlyeXQ\nok")
    assert [h.kind for h in hits] == ["license-token"]
    assert hits[0].line_no == 2
    assert "o2d1c2Vy" not in hits[0].preview  # preview never carries secret bytes


def test_scanner_flags_uuid_only_in_secret_context() -> None:
    flagged = find_hits('OFFLINE_LICENSE_TOKEN="87086212-1234-5678-9012-abcdef123456"')
    assert [h.kind for h in flagged] == ["secret-context-uuid"]
    # run/database/device ids are legitimate evidence content — never flagged.
    assert find_hits('{"run_id": "4964902d-3883-483b-b611-c786f29f34a4"}') == []
    assert find_hits('database_id=b2c6f1fd-3951-4e90-ae33-cbda6a7a7102') == []


def test_scanner_extra_prefix_env(fake_token_prefix: str) -> None:
    hits = find_hits(f"token starts {fake_token_prefix}QUJDREVGRw== and more")
    assert [h.kind for h in hits] == ["declared-prefix"]


def test_scrub_redacts_token_runs() -> None:
    from secret_scan import scrub_text

    dirty = 'env: SANDBOX_SECRET_DITTO_OFFLINE_LICENSE=o2d1c2VyX3RlQ3JldF9UY0V4cGlyeQ== end'
    clean, count = scrub_text(dirty)
    assert count == 1
    assert LICENSE_TOKEN_PREFIX not in clean
    assert "[REDACTED]" in clean


@pytest.mark.parametrize("tracked_path", tracked_edge_model_files(), ids=lambda p: p.name)
def test_no_token_material_in_tracked_edge_model_files(tracked_path: Path) -> None:
    hits = scan_file(tracked_path)
    assert hits == [], (
        f"license-token material leaked into tracked evidence: {tracked_path}:"
        f"{[h.line_no for h in hits]}"
    )
