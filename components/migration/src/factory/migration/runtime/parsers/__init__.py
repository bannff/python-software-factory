"""KiroCrew ``kirocrew-v1`` per-kind parsers over the trusted snapshot.

Parsers read ONLY the trusted temp copy produced by ``source_snapshot`` and
emit strict immutable records + a bounded ``KindReport``. Unknown schema
versions fail their kind (never the whole snapshot); malformed records produce
content-free diagnostics. No embeddings, deleted rows, events, secrets, or raw
runtime fields ever leave a parser.
"""
from __future__ import annotations

import json
from typing import Any, Iterator

from ..source_models import (
    MAX_DIAGNOSTICS, Diagnostic, KindReport, ReasonCode, SourceKind, sha256_hex,
)


def kind_digest(kind: SourceKind, identities: list[str]) -> str:
    """Deterministic digest over the sorted record identities of a kind."""
    payload = kind.value + "\n" + "\n".join(sorted(identities))
    return sha256_hex(payload)


def build_report(
    kind: SourceKind, found: int, identities: list[str],
    diagnostics: list[Diagnostic],
) -> KindReport:
    return KindReport(
        kind=kind,
        found=found,
        eligible=len(identities),
        excluded=len(diagnostics),
        digest=kind_digest(kind, identities),
        diagnostics=tuple(diagnostics[:MAX_DIAGNOSTICS]),
    )


def iter_jsonl(text: str) -> Iterator[tuple[int, str, Any]]:
    """Yield ``(line_no, raw_line, parsed_or_None)`` with per-line isolation.

    A malformed line yields ``parsed=None`` so callers emit a MALFORMED
    diagnostic and continue — one bad line never poisons the file.
    """
    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            yield line_no, raw, json.loads(stripped)
        except (ValueError, RecursionError):
            yield line_no, raw, None


def malformed(kind: SourceKind, detail: str = "") -> Diagnostic:
    return Diagnostic(kind=kind, reason=ReasonCode.MALFORMED, detail=detail[:200])


__all__ = ["kind_digest", "build_report", "iter_jsonl", "malformed"]
