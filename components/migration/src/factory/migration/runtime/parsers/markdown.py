"""Parse supported KiroCrew memory markdown from the trusted snapshot.

Handles ``workspace/memory/preferences.md``, ``projects.md``, and
``workspace/memory/history/*.md`` under the same size controls as the snapshot.
Each file becomes one immutable record keyed by relative path; empty files are
excluded. Content is imported verbatim (bounded) — redaction to a preview
sample happens at the preview boundary, not here.
"""
from __future__ import annotations

from pathlib import Path

from ..source_models import (
    MAX_TEXT_CHARS, Diagnostic, KindReport, ReasonCode, SafeMarkdown,
    SourceKind, identity_of,
)
from . import build_report

_KIND = SourceKind.MARKDOWN
_DOCS: tuple[tuple[str, str], ...] = (
    ("workspace/memory/preferences.md", "preferences"),
    ("workspace/memory/projects.md", "projects"),
)
_HISTORY_DIR = "workspace/memory/history"


def _read(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return text


def _record(rel: str, doc: str, content: str) -> SafeMarkdown:
    return SafeMarkdown(
        identity=identity_of("markdown", rel),
        doc=doc,  # type: ignore[arg-type]
        rel_path=rel,
        content=content,
    )


def parse_markdown(snapshot_dir: Path) -> tuple[list[SafeMarkdown], KindReport]:
    snapshot_dir = Path(snapshot_dir)
    records: list[SafeMarkdown] = []
    diags: list[Diagnostic] = []
    found = 0
    candidates: list[tuple[str, str]] = list(_DOCS)
    history = snapshot_dir / _HISTORY_DIR
    if history.is_dir():
        for md in sorted(history.glob("*.md")):
            candidates.append((f"{_HISTORY_DIR}/{md.name}", "history"))
    for rel, doc in candidates:
        path = snapshot_dir / rel
        if not path.exists():
            continue
        found += 1
        content = _read(path)
        if content is None or len(content) > MAX_TEXT_CHARS:
            diags.append(Diagnostic(kind=_KIND, reason=ReasonCode.MALFORMED, detail=doc))
            continue
        if not content.strip():
            diags.append(Diagnostic(kind=_KIND, reason=ReasonCode.EMPTY, detail=rel[:200]))
            continue
        records.append(_record(rel, doc, content))
    identities = [r.identity for r in records]
    return records, build_report(_KIND, found, identities, diags)


__all__ = ["parse_markdown"]
