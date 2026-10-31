#!/usr/bin/env python3
"""Git pre-commit hook: block commits that contain license-token material.

Wired via core.hooksPath=.beads/hooks — appended to the beads-managed
pre-commit script. Scans staged diffs (added/modified files, full staged
content of text files) with scripts/hooks/secret_scan.py patterns.

Override for legitimate fixtures: SECRET_SCAN_ALLOW=1 git commit ...
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from secret_scan import find_hits  # noqa: E402

MAX_FILE_BYTES = 5 * 1024 * 1024


def staged_files() -> list[Path]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    return [Path(line) for line in result.stdout.splitlines() if line]


def main() -> int:
    if os.environ.get("SECRET_SCAN_ALLOW"):
        return 0
    flagged: list[dict[str, object]] = []
    for path in staged_files():
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if "\x00" in text[:4096]:
            continue
        hits = find_hits(text)
        if hits:
            flagged.append({
                "file": str(path),
                "lines": [h.line_no for h in hits],
                "kinds": sorted({h.kind for h in hits}),
            })
    if flagged:
        print(json.dumps({
            "error": "secret-scan: possible license token / credential material in staged files",
            "hint": "store secrets in the macOS keychain and reference the 0600 file "
                    "under ~/.config/python-factory/secrets/ via env var; "
                    "override with SECRET_SCAN_ALLOW=1 only for synthetic fixtures",
            "files": flagged,
        }, indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
