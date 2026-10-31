"""Cross-brick contract tests for deterministic Migration target preparation."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from factory.lessons.mcp.contracts import ImportLessonInput
from factory.lessons.runtime.identity import import_target_digest
from factory.memory.mcp.contracts.migration_import import MemoryImportInput
from factory.memory.runtime.migration_import import canonical_target_digest
from factory.mcp_utils.interface import MigrationImportBinding
from factory.migration.runtime.plan_records import PlanRecord
from factory.migration.runtime.receipt_models import PlanIdentity
from factory.migration.runtime.source_models import (
    SafeLesson, SafeMarkdown, SafeMemory, SafeSchedule, SourceKind, identity_of,
)
from factory.migration.runtime.target_prepare import (
    TargetPreparationError, prepare_target_call,
)
from factory.scheduler.mcp.import_contracts import SchedulerImportInput
from factory.scheduler.runtime.import_records import derive_schedule_id, target_digest


def _plan() -> PlanIdentity:
    return PlanIdentity(
        tenant_id="tenant", owner_id="owner", adapter="kirocrew-v1",
        source_fingerprint="a" * 64, plan_digest="sha256:" + "b" * 64,
        kinds=("memory", "lessons", "schedules", "markdown"),
    )


def _record(kind: SourceKind, payload) -> PlanRecord:
    return PlanRecord.from_source(_plan(), kind, payload)


def test_memory_payload_and_digest_match_target_owner() -> None:
    payload = SafeMemory(
        kind="semantic", identity=identity_of("semantic", "pref"),
        key="pref", content="Use typed tools", tags=("ops", "ops", "team"),
    )
    call = prepare_target_call(_record(SourceKind.MEMORY, payload))
    args = call.arguments.model_dump()
    assert MemoryImportInput.model_validate(args)
    assert args["plan_digest"] == "b" * 64
    assert args["tags"] == ["ops", "team"]
    assert args["target_digest"] == canonical_target_digest(
        tenant_id="tenant", owner_id="owner", kind="memory",
        subtype="semantic", content="Use typed tools", key="pref",
        tags=["ops", "team"],
    )
    assert call.invocation_arguments() == args
    assert MigrationImportBinding(**call.migration_binding())
    assert set(call.migration_binding()) == {
        "tenant_id", "owner_id", "source_adapter", "source_fingerprint",
        "plan_digest", "kind", "source_record_id", "target_digest",
    }


def test_markdown_maps_to_memory_without_source_path() -> None:
    payload = SafeMarkdown(
        identity=identity_of("markdown", "preferences"), doc="preferences",
        rel_path="workspace/memory/preferences.md", content="Prefer concise output",
    )
    call = prepare_target_call(_record(SourceKind.MARKDOWN, payload))
    args = call.arguments.model_dump()
    assert MemoryImportInput.model_validate(args)
    assert call.source_kind is SourceKind.MARKDOWN
    assert args["key"].startswith("markdown:preferences:")
    assert "rel_path" not in args and "workspace" not in str(args)


def test_lesson_payload_and_digest_match_target_owner() -> None:
    payload = SafeLesson(
        identity=identity_of("lesson", "rule"), rule="Always cite sources",
        category="custom", negative="Never invent one", repo_scope="acme/repo",
        origin="jsonl",
    )
    call = prepare_target_call(_record(SourceKind.LESSONS, payload))
    args = call.arguments.model_dump()
    assert ImportLessonInput.model_validate(args)
    assert args["category"] == "knowledge"
    assert args["target_digest"] == import_target_digest(
        "tenant", "owner", "kirocrew-v1", payload.identity,
        payload.rule, payload.negative, "knowledge", "acme/repo", (),
    )


@pytest.mark.parametrize("payload", [
    SafeSchedule(
        identity=identity_of("cron", "interval"), name="digest", message="review",
        schedule_kind="every", every_secs=300, paused=True,
    ),
    SafeSchedule(
        identity=identity_of("cron", "once"), name="once", schedule_kind="at",
        at_ts=datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp(), paused=True,
    ),
    SafeSchedule(
        identity=identity_of("cron", "cron"), name="cron", schedule_kind="cron",
        cron_expr="17 3 * * *", timezone="UTC", skip_dates=("2027-01-02",),
        strict_schedule=True, paused=True,
    ),
])
def test_schedule_payload_and_digest_match_target_owner(payload: SafeSchedule) -> None:
    call = prepare_target_call(_record(SourceKind.SCHEDULES, payload))
    args = call.arguments.model_dump()
    validated = SchedulerImportInput.model_validate(args)
    schedule_id = derive_schedule_id("kirocrew-v1", payload.identity)
    definition = validated.schedule.model_dump(mode="json")
    assert args["target_digest"] == target_digest(
        "tenant", "owner", schedule_id, definition,
    )
    assert call.brick == "scheduler" and call.tool == "scheduler_import_record"


def test_target_ingress_limit_returns_fixed_safe_error() -> None:
    payload = SafeMemory(
        kind="episodic", identity=identity_of("episodic", "large"),
        content="x" * 8193,
    )
    with pytest.raises(TargetPreparationError) as error:
        prepare_target_call(_record(SourceKind.MEMORY, payload))
    assert error.value.safe == "migration_target_record_unsupported"
