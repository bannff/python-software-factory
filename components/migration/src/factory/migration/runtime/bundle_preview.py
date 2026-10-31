"""Owner-bound ``companion-x-v1`` bundle preview — same receipt/plan engine
as ``PreviewRuntime`` (kirocrew-v1), different staging+parsing front end.

Deliberately mirrors ``PreviewRuntime.preview()``'s exact shape (same
``PreviewResult``, same receipt binding, same all-or-nothing failure
posture) so `mcp/operational.py` can dispatch to either by adapter name
with no downstream difference — the apply/target engine (`apply_execution.py`,
`target_prepare.py`) is unmodified and adapter-agnostic already.
"""
from __future__ import annotations

from dataclasses import dataclass

from .bundle_stage import BundleStageError, stage_bundle
from .parsers.bundle import bundle_kinds, parse_bundle_kind, unsupported_bundle_kinds
from .plan_records import PlanRecord
from .ports import ReceiptStore
from .receipt_models import CommitStatus, PlanIdentity
from .source_models import (
    KindReport, PreviewSample, SafeLesson, SafeMemory, SafeSchedule, redact, sha256_hex,
)

_ADAPTER = "companion-x-v1"


class BundlePreviewUnavailable(RuntimeError):
    """Fixed safe failure for absent, unsafe, or conflicting bundle preview."""


@dataclass(frozen=True)
class BundlePreviewResult:
    plan: PlanIdentity
    status: CommitStatus
    reports: tuple[KindReport, ...]
    samples: tuple[PreviewSample, ...]
    unsupported_kinds: tuple[str, ...]


def _sample(kind, record) -> PreviewSample:
    if isinstance(record, SafeMemory):
        text = record.content
    elif isinstance(record, SafeLesson):
        text = record.rule
    elif isinstance(record, SafeSchedule):
        text = record.name
    else:  # pragma: no cover - parser contract guard
        raise TypeError("unsupported bundle preview record")
    return PreviewSample(kind=kind, identity=record.identity, sample=redact(text))


class BundlePreviewRuntime:
    """Build redacted immutable plans from a companion-x-v1 bundle file."""

    def __init__(self, bundle_path_resolver, receipts: ReceiptStore) -> None:
        self._resolve = bundle_path_resolver
        self.receipts = receipts

    def preview(
        self, tenant_id: str, owner_id: str, bundle_ref: str,
        requested_kinds: tuple[str, ...] | None,
    ) -> BundlePreviewResult:
        try:
            path = self._resolve(bundle_ref)
        except (OSError, ValueError) as exc:
            raise BundlePreviewUnavailable("migration_bundle_unavailable") from exc
        try:
            bundle = stage_bundle(path)
        except BundleStageError as exc:
            raise BundlePreviewUnavailable(f"migration_{exc.code}") from exc
        available = bundle_kinds(bundle)
        selected = tuple(k for k in (requested_kinds or available) if k in available)
        if not selected:
            raise BundlePreviewUnavailable("migration_bundle_kinds_unavailable")
        unsupported = unsupported_bundle_kinds(bundle)
        reports: list[KindReport] = []
        samples: list[PreviewSample] = []
        parsed: list[tuple[KindReport, list]] = []
        for bundle_key in selected:
            if bundle_key in unsupported:
                continue
            records, report = parse_bundle_kind(bundle, bundle_key)
            parsed.append((report, records))
            reports.append(report)
            samples.extend(_sample(report.kind, row) for row in records[:3])
        source_fingerprint = bundle["content_digest"].removeprefix("sha256:")
        payload = "\n".join([source_fingerprint, *(f"{r.kind.value}:{r.digest}" for r in reports)])
        plan = PlanIdentity(
            tenant_id=tenant_id, owner_id=owner_id, adapter=_ADAPTER,
            source_fingerprint=source_fingerprint,
            plan_digest=f"sha256:{sha256_hex(payload)}",
            kinds=tuple(report.kind.value for report in reports),
        )
        try:
            for report, records in parsed:
                material = tuple(PlanRecord.from_source(plan, report.kind, row) for row in records)
                commits = self.receipts.save_plan_records(plan, material)
                if any(c.status is CommitStatus.CONFLICT for c in commits):
                    raise BundlePreviewUnavailable("migration_bundle_plan_conflict")
            commit = self.receipts.bind_plan(plan)
        except BundlePreviewUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — normalize storage adapters
            raise BundlePreviewUnavailable("migration_bundle_receipt_unavailable") from exc
        if commit.status is CommitStatus.CONFLICT:
            raise BundlePreviewUnavailable("migration_bundle_plan_conflict")
        return BundlePreviewResult(
            plan=plan, status=commit.status, reports=tuple(reports),
            samples=tuple(samples), unsupported_kinds=unsupported,
        )


__all__ = ["BundlePreviewResult", "BundlePreviewRuntime", "BundlePreviewUnavailable"]
