"""Immutable Migration plan material over public Storage SQLStore."""
from __future__ import annotations

from ..plan_records import PlanRecord, PlanRecordCommit, parse_payload
from ..receipt_models import CommitStatus, PlanCommit, PlanIdentity
from ..source_models import SourceKind

_PLANS = """CREATE TABLE IF NOT EXISTS migration_plans (
    tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, adapter TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL, plan_digest TEXT NOT NULL,
    kinds TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (tenant_id, owner_id, adapter, source_fingerprint, plan_digest))"""
_RECORDS = """CREATE TABLE IF NOT EXISTS migration_plan_records (
    tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, adapter TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL, plan_digest TEXT NOT NULL, kind TEXT NOT NULL,
    source_record_id TEXT NOT NULL, payload_json TEXT NOT NULL,
    payload_digest TEXT NOT NULL,
    PRIMARY KEY (tenant_id, owner_id, adapter, source_fingerprint, plan_digest,
                 kind, source_record_id))"""


def _params(plan: PlanIdentity | PlanRecord) -> dict[str, str]:
    return {
        "tenant_id": plan.tenant_id, "owner_id": plan.owner_id,
        "adapter": plan.adapter, "source_fingerprint": plan.source_fingerprint,
        "plan_digest": plan.plan_digest,
    }


def _record(row) -> PlanRecord:
    kind = SourceKind(row["kind"])
    record = PlanRecord(
        tenant_id=row["tenant_id"], owner_id=row["owner_id"],
        adapter=row["adapter"], source_fingerprint=row["source_fingerprint"],
        plan_digest=row["plan_digest"], kind=kind,
        source_record_id=row["source_record_id"],
        payload=parse_payload(kind, row["payload_json"]),
    )
    if record.payload_digest != row["payload_digest"]:
        raise ValueError("migration plan record digest mismatch")
    return record


class PlanStoreSqlMixin:
    """SQL methods mixed into the receipt adapter to preserve SRP/LOC limits."""

    def _initialize_plans(self) -> None:
        self._sql.execute(_PLANS)
        self._sql.execute(_RECORDS)

    def bind_plan(self, plan: PlanIdentity) -> PlanCommit:
        params = {**_params(plan), "kinds": ",".join(plan.kinds)}
        result = self._sql.execute(
            "INSERT OR IGNORE INTO migration_plans (tenant_id, owner_id, adapter, "
            "source_fingerprint, plan_digest, kinds) VALUES (:tenant_id, :owner_id, "
            ":adapter, :source_fingerprint, :plan_digest, :kinds)", params)
        if result.row_count == 1:
            return PlanCommit(status=CommitStatus.COMMITTED, plan=plan)
        existing = self.get_plan(**_params(plan))
        if existing is None:
            raise RuntimeError("migration plan commit unavailable")
        status = (CommitStatus.REPLAYED if existing.kinds == plan.kinds
                  else CommitStatus.CONFLICT)
        return PlanCommit(status=status, plan=existing)

    def get_plan(self, tenant_id: str, owner_id: str, adapter: str,
                 source_fingerprint: str, plan_digest: str) -> PlanIdentity | None:
        row = self._sql.fetch_one(
            "SELECT * FROM migration_plans WHERE tenant_id=:tenant_id AND "
            "owner_id=:owner_id AND adapter=:adapter AND "
            "source_fingerprint=:source_fingerprint AND plan_digest=:plan_digest",
            locals())
        if not row:
            return None
        kinds = tuple(row["kinds"].split(",")) if row["kinds"] else ()
        return PlanIdentity(
            tenant_id=row["tenant_id"], owner_id=row["owner_id"],
            adapter=row["adapter"], source_fingerprint=row["source_fingerprint"],
            plan_digest=row["plan_digest"], kinds=kinds)

    def find_plan(self, tenant_id: str, owner_id: str, adapter: str,
                  plan_digest: str) -> PlanIdentity | None:
        rows = self._sql.fetch_all(
            "SELECT * FROM migration_plans WHERE tenant_id=:tenant_id AND "
            "owner_id=:owner_id AND adapter=:adapter AND plan_digest=:plan_digest",
            {"tenant_id": tenant_id, "owner_id": owner_id, "adapter": adapter,
             "plan_digest": plan_digest})
        if len(rows) > 1:
            raise RuntimeError("migration plan identity ambiguous")
        if not rows:
            return None
        row = rows[0]
        return PlanIdentity(
            tenant_id=row["tenant_id"], owner_id=row["owner_id"],
            adapter=row["adapter"], source_fingerprint=row["source_fingerprint"],
            plan_digest=row["plan_digest"],
            kinds=tuple(row["kinds"].split(",")) if row["kinds"] else (),
        )

    def save_plan_records(
        self, plan: PlanIdentity, records: tuple[PlanRecord, ...],
    ) -> tuple[PlanRecordCommit, ...]:
        commits = []
        for record in records:
            if _params(plan) != _params(record):
                raise ValueError("plan record authority mismatch")
            if record.kind.value not in plan.kinds:
                raise ValueError("plan record kind not selected")
            params = {
                **record.model_dump(mode="json", exclude={"payload"}),
                "kind": record.kind.value, "payload_json": record.payload_json,
                "payload_digest": record.payload_digest,
            }
            result = self._sql.execute(
                "INSERT OR IGNORE INTO migration_plan_records (tenant_id, owner_id, "
                "adapter, source_fingerprint, plan_digest, kind, source_record_id, "
                "payload_json, payload_digest) VALUES (:tenant_id, :owner_id, :adapter, "
                ":source_fingerprint, :plan_digest, :kind, :source_record_id, "
                ":payload_json, :payload_digest)", params)
            existing = record if result.row_count == 1 else self.find_plan_record(
                **_params(plan), kind=record.kind, source_record_id=record.source_record_id)
            if existing is None:
                raise RuntimeError("migration plan record commit unavailable")
            status = (CommitStatus.COMMITTED if result.row_count == 1 else
                      CommitStatus.REPLAYED if (existing.payload_digest == record.payload_digest
                                                and existing.payload_json == record.payload_json)
                      else CommitStatus.CONFLICT)
            commits.append(PlanRecordCommit(status=status, record=existing))
        return tuple(commits)

    def find_plan_record(
        self, tenant_id: str, owner_id: str, adapter: str, source_fingerprint: str,
        plan_digest: str, kind: SourceKind, source_record_id: str,
    ) -> PlanRecord | None:
        row = self._sql.fetch_one(
            "SELECT * FROM migration_plan_records WHERE tenant_id=:tenant_id AND "
            "owner_id=:owner_id AND adapter=:adapter AND "
            "source_fingerprint=:source_fingerprint AND plan_digest=:plan_digest AND "
            "kind=:kind AND source_record_id=:source_record_id",
            {"tenant_id": tenant_id, "owner_id": owner_id, "adapter": adapter,
             "source_fingerprint": source_fingerprint, "plan_digest": plan_digest,
             "kind": kind.value, "source_record_id": source_record_id})
        return _record(row) if row else None

    def list_plan_records(
        self, tenant_id: str, owner_id: str, adapter: str, source_fingerprint: str,
        plan_digest: str, kind: SourceKind, offset: int, limit: int,
    ) -> list[PlanRecord]:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("invalid plan record page")
        rows = self._sql.fetch_all(
            "SELECT * FROM migration_plan_records WHERE tenant_id=:tenant_id AND "
            "owner_id=:owner_id AND adapter=:adapter AND "
            "source_fingerprint=:source_fingerprint AND plan_digest=:plan_digest AND "
            "kind=:kind ORDER BY source_record_id LIMIT :limit OFFSET :offset",
            {"tenant_id": tenant_id, "owner_id": owner_id, "adapter": adapter,
             "source_fingerprint": source_fingerprint, "plan_digest": plan_digest,
             "kind": kind.value, "offset": offset, "limit": limit})
        return [_record(row) for row in rows]


__all__ = ["PlanStoreSqlMixin"]
