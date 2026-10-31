"""Secret-hygiene scanner: source of truth for license-token patterns.

Shared engine for three guardrails:
- ``scripts/hooks/precommit_secret_scan.py`` (git pre-commit via .beads/hooks)
- ``scripts/test/test_secret_scan_guard.py`` (CI core-tests)
- the takeover demo driver's evidence scrub (edge-mesh-demo/run_takeover_demo.py)

Patterns target the Ditto offline license token family (DTLV tag 0x79 — every
such token's base64 begins ``o2d1c2Vy``) and UUID-format credentials in
secret-bearing key contexts (e.g. portal Development tokens pasted into env
dumps). Bare UUIDs are deliberately NOT flagged: run IDs, database IDs and
device IDs are UUIDs and appear throughout legitimate evidence files.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

# Base64 of the DTLV tag-0x79 header every Ditto offline/dev license starts with.
LICENSE_TOKEN_PREFIX = "o2d1c2Vy"

# UUID only when bound to a secret-looking key. `run_id=`, `database_id=`,
# `device_id=` etc. never match; `*_LICENSE=`, `*_TOKEN=`, `*_SECRET=` do.
SECRET_CONTEXT_UUID = re.compile(
    r"(?i)(?:\b|_)(license|token|secret|password|api[_-]?key)\w*\s*[:=]\s*[\"']?"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)

# Env/setting used to register additional exact token prefixes at runtime
# (e.g. the real token's prefix locally, a fake one in tests). Minimum length
# 8 keeps accidental short values from nuking every commit.
EXTRA_PREFIXES_ENV = "SECRET_SCAN_TOKEN_PREFIXES"
REDACTED = "[REDACTED]"

# Whole-token runs keep the base64 residue after a prefix from surviving a scrub.
_TOKEN_RUN = re.compile(
    re.escape(LICENSE_TOKEN_PREFIX) + r"[A-Za-z0-9+/=_-]*"
)

MAX_SCAN_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class SecretHit:
    line_no: int
    kind: str
    preview: str  # always redacted; never carries secret bytes


def extra_prefixes() -> tuple[str, ...]:
    raw = os.environ.get(EXTRA_PREFIXES_ENV, "")
    return tuple(
        p.strip() for p in raw.split(",") if len(p.strip()) >= 8
    )


def find_hits(text: str) -> list[SecretHit]:
    """Line-level detection. Returns one hit per flagged line."""
    prefixes = extra_prefixes()
    hits: list[SecretHit] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _TOKEN_RUN.search(line):
            hits.append(SecretHit(line_no, "license-token", REDACTED))
        elif SECRET_CONTEXT_UUID.search(line):
            hits.append(SecretHit(line_no, "secret-context-uuid", REDACTED))
        elif any(p in line for p in prefixes):
            hits.append(SecretHit(line_no, "declared-prefix", REDACTED))
    return hits


def scrub_text(text: str) -> tuple[str, int]:
    """Redact detected secrets in place. Returns (clean_text, replacements)."""
    count = len(_TOKEN_RUN.findall(text))

    def _uuid_sub(match: re.Match[str]) -> str:
        return f"{match.group(1)}={REDACTED}"

    text, uuid_count = SECRET_CONTEXT_UUID.subn(_uuid_sub, text)
    count += uuid_count

    prefixes = extra_prefixes()
    for prefix in prefixes:
        run = re.compile(re.escape(prefix) + r"[A-Za-z0-9+/=_-]*")
        count += len(run.findall(text))
        text = run.sub(REDACTED, text)

    if count:
        text = _TOKEN_RUN.sub(REDACTED, text)
    return text, count


def scan_file(path: Path) -> list[SecretHit]:
    """Scan one file, capped at MAX_SCAN_BYTES. Binary-ish files are skipped."""
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return []
        text = path.read_text(errors="replace")
    except OSError:
        return []
    if "\x00" in text[:4096]:
        return []
    return find_hits(text)
