"""Disk-backed owner-scoped store for authored prompts (CAS on ``revision``)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from factory.mcp_utils.interface import TypedToolFailure

from .adapters.crew_store_base import _owner_lock, authority_hash
from .prompt_models import PromptArg, PromptRecord, check_template


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DiskPromptStore:
    """One ``prompts.json`` per (tenant, owner), written atomically under a lock."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def _path(self, tenant_id: str, owner_id: str) -> Path:
        return self._root / authority_hash(tenant_id, owner_id) / "prompts.json"

    def _load(self, tenant_id: str, owner_id: str) -> dict[str, PromptRecord]:
        path = self._path(tenant_id, owner_id)
        if not path.exists():
            return {}
        rows = json.loads(path.read_text())
        return {r["prompt_id"]: PromptRecord.model_validate(r) for r in rows}

    def _save(self, tenant_id: str, owner_id: str, records: dict[str, PromptRecord]) -> None:
        path = self._path(tenant_id, owner_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps([r.model_dump(mode="json") for r in records.values()]))
        with open(tmp, "rb") as handle:
            os.fsync(handle.fileno())
        os.replace(tmp, path)

    def list(self, tenant_id: str, owner_id: str) -> list[PromptRecord]:
        with _owner_lock(f"prompts:{tenant_id}:{owner_id}"):
            return sorted(self._load(tenant_id, owner_id).values(), key=lambda r: r.prompt_id)

    def get(self, tenant_id: str, owner_id: str, prompt_id: str) -> PromptRecord:
        with _owner_lock(f"prompts:{tenant_id}:{owner_id}"):
            record = self._load(tenant_id, owner_id).get(prompt_id)
        if record is None:
            raise TypedToolFailure("prompt_not_found", prompt_id)
        return record

    def create(self, tenant_id: str, owner_id: str, prompt_id: str, description: str,
               arguments: tuple[PromptArg, ...], template: str) -> PromptRecord:
        check_template(template, arguments)
        with _owner_lock(f"prompts:{tenant_id}:{owner_id}"):
            records = self._load(tenant_id, owner_id)
            if prompt_id in records:
                raise TypedToolFailure("prompt_exists", prompt_id)
            record = PromptRecord(
                tenant_id=tenant_id, owner_id=owner_id, prompt_id=prompt_id, description=description,
                arguments=arguments, template=template, created_at=_now(), updated_at=_now(),
            )
            self._save(tenant_id, owner_id, {**records, prompt_id: record})
            return record

    def update(self, tenant_id: str, owner_id: str, prompt_id: str, expected_revision: int, *,
               description: str | None = None, arguments: tuple[PromptArg, ...] | None = None,
               template: str | None = None) -> PromptRecord:
        with _owner_lock(f"prompts:{tenant_id}:{owner_id}"):
            records = self._load(tenant_id, owner_id)
            current = records.get(prompt_id)
            if current is None:
                raise TypedToolFailure("prompt_not_found", prompt_id)
            if current.revision != expected_revision:
                raise TypedToolFailure("prompt_revision_conflict", prompt_id)
            merged = {
                "description": current.description if description is None else description,
                "arguments": current.arguments if arguments is None else arguments,
                "template": current.template if template is None else template,
            }
            check_template(merged["template"], merged["arguments"])
            record = current.model_copy(update={
                **merged, "revision": current.revision + 1, "updated_at": _now(),
            })
            self._save(tenant_id, owner_id, {**records, prompt_id: record})
            return record

    def delete(self, tenant_id: str, owner_id: str, prompt_id: str) -> None:
        with _owner_lock(f"prompts:{tenant_id}:{owner_id}"):
            records = self._load(tenant_id, owner_id)
            if prompt_id not in records:
                raise TypedToolFailure("prompt_not_found", prompt_id)
            self._save(tenant_id, owner_id, {k: v for k, v in records.items() if k != prompt_id})


__all__ = ["DiskPromptStore"]
