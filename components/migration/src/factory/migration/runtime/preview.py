"""Owner-bound KiroCrew source preview over trusted snapshots and receipts."""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from .parsers.lessons import parse_lessons
from .parsers.markdown import parse_markdown
from .parsers.memory import parse_memory
from .parsers.schedules import parse_schedules
from .plan_records import PlanRecord
from .ports import ReceiptStore
from .receipt_models import CommitStatus, PlanIdentity
from .source_models import (
    Diagnostic, KindReport, PreviewSample, SafeLesson, SafeMarkdown,
    SafeMemory, SafeSchedule, SnapshotManifest, SourceKind, redact, sha256_hex,
)
from .source_snapshot import SnapshotError, stage_snapshot

_ADAPTER = "kirocrew-v1"
_PARSERS = {
    SourceKind.MEMORY: parse_memory, SourceKind.LESSONS: parse_lessons,
    SourceKind.SCHEDULES: parse_schedules, SourceKind.MARKDOWN: parse_markdown,
}


class PreviewUnavailable(RuntimeError):
    """Fixed safe failure for absent, unsafe, or conflicting preview state."""


@dataclass(frozen=True)
class PreviewResult:
    manifest: SnapshotManifest
    plan: PlanIdentity
    status: CommitStatus
    reports: tuple[KindReport, ...]
    samples: tuple[PreviewSample, ...]
    snapshot_diagnostics: tuple[Diagnostic, ...]


def _sample(kind: SourceKind, record: object) -> PreviewSample:
    if isinstance(record, SafeMemory):
        text = record.content
    elif isinstance(record, SafeLesson):
        text = record.rule
    elif isinstance(record, SafeSchedule):
        text = record.name
    elif isinstance(record, SafeMarkdown):
        text = record.content
    else:  # pragma: no cover - parser contract guard
        raise TypeError("unsupported preview record")
    return PreviewSample(kind=kind, identity=record.identity, sample=redact(text))


def _error_kind(error: SnapshotError) -> SourceKind:
    rel = error.rel_path
    if rel == "memory.db":
        return SourceKind.MEMORY
    if rel == "lessons.jsonl":
        return SourceKind.LESSONS
    if rel in {"crons.json", "cron/jobs.json"}:
        return SourceKind.SCHEDULES
    return SourceKind.MARKDOWN


class PreviewRuntime:
    """Build redacted immutable plans without writing any target brick."""

    def __init__(self, root: Path | None, receipts: ReceiptStore) -> None:
        self.root = root
        self.receipts = receipts

    def preview(
        self, tenant_id: str, owner_id: str, kinds: tuple[SourceKind, ...],
    ) -> PreviewResult:
        root = self.root
        if root is None or not root.is_absolute() or root.is_symlink() or not root.is_dir():
            raise PreviewUnavailable("migration source unavailable")
        selected = tuple(dict.fromkeys(kinds))
        if not selected:
            raise PreviewUnavailable("migration kinds unavailable")
        try:
            with tempfile.TemporaryDirectory(prefix="migration-preview-") as tmp:
                manifest, errors = stage_snapshot(root, Path(tmp))
                reports: list[KindReport] = []
                samples: list[PreviewSample] = []
                for kind in selected:
                    records, report = _PARSERS[kind](Path(tmp))
                    reports.append(report)
                    samples.extend(_sample(kind, row) for row in records[:3])
                payload = "\n".join(
                    [manifest.digest, *(f"{r.kind.value}:{r.digest}" for r in reports)])
                plan = PlanIdentity(
                    tenant_id=tenant_id, owner_id=owner_id, adapter=_ADAPTER,
                    source_fingerprint=manifest.digest,
                    plan_digest=f"sha256:{sha256_hex(payload)}",
                    kinds=tuple(kind.value for kind in selected),
                )
                try:
                    for kind in selected:
                        records, _report = _PARSERS[kind](Path(tmp))
                        material = tuple(
                            PlanRecord.from_source(plan, kind, row) for row in records)
                        commits = self.receipts.save_plan_records(plan, material)
                        if any(c.status is CommitStatus.CONFLICT for c in commits):
                            raise PreviewUnavailable("migration plan conflict")
                    commit = self.receipts.bind_plan(plan)
                except PreviewUnavailable:
                    raise
                except Exception as exc:  # noqa: BLE001 — normalize storage adapters
                    raise PreviewUnavailable("migration receipt unavailable") from exc
        except PreviewUnavailable:
            raise
        except (OSError, ValueError) as exc:
            raise PreviewUnavailable("migration source unavailable") from exc
        if commit.status is CommitStatus.CONFLICT:
            raise PreviewUnavailable("migration plan conflict")
        diagnostics = tuple(
            Diagnostic(kind=_error_kind(error), reason=error.reason) for error in errors)
        return PreviewResult(
            manifest=manifest, plan=plan, status=commit.status,
            reports=tuple(reports), samples=tuple(samples),
            snapshot_diagnostics=diagnostics,
        )


__all__ = ["PreviewResult", "PreviewRuntime", "PreviewUnavailable"]
