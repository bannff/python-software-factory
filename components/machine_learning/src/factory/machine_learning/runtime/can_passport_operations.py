"""Reference-gated CAN passport issuance and conformance."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from .can_evals_binding import verify_evaluation_pointers, verify_evaluation_records
from .can_feature_contract import load_can_feature_contract
from .can_legacy_binding import build_can_legacy_binding
from .can_passport_promotion import promote_passports
from .can_passports import CanPassportContext, issue_can_model_passport
from .can_training_seal_binding import require_training_model_seal
from .can_training_job_rehydrate import rehydrate_training_job
from .model_passport import ConformanceEvidence
from .passport_artifacts import file_artifact_ref
from .passport_store_models import ModelPassportRef
from .passport_service import ModelPassportService


def issue_passports(
    context: Any, *, training_terminal: dict[str, Any],
    evaluation_pointers: list[dict[str, Any]], invoker: Any,
    service: ModelPassportService, passport_root: Path,
) -> dict[str, Any]:
    """Issue candidates only after family-declared adequacy verification."""
    dataset, rows = _training_parts(training_terminal)
    from .can_family_specs import family_spec
    if evaluation_pointers:
        verified = verify_evaluation_records(invoker, evaluation_pointers)
        _require_record_cases(verified, rows)
    else:
        if any(family_spec(row["model_family"]).evaluation_required for row in rows):
            raise ValueError("this model family requires verified Evals pointers")
        verified = ()
    pointers = tuple(item.pointer for item in verified)
    base_context = _passport_context(dataset, passport_root, pointers)
    records = []
    for row in rows:
        can_id, refs = row["can_id"], row["artifact_refs"]
        row_bindings = tuple(
            record.binding_for(str(row["job_id"]), str(can_id))
            for record in verified
        )
        contract = load_can_feature_contract(refs["contract"]["uri"])
        job, spec, refs, info = rehydrate_training_job(row)
        legacy = build_can_legacy_binding(
            dataset, can_id=can_id, rank=row["rank"], row=row,
        )
        require_training_model_seal(row, passport_root)
        inputs = {
            "job_id": job.id, "can_id": can_id, "rank": row["rank"], "refs": refs,
            "evaluation_pointers": [item.model_dump(mode="json") for item in pointers],
            "evaluation_adequacy": [
                item.model_dump(mode="json") for item in row_bindings
            ],
            "legacy_binding": legacy.model_dump(mode="json"),
        }

        def publish(_effect_id: str) -> dict[str, Any]:
            _, publication = issue_can_model_passport(
                context=replace(
                    base_context, legacy_binding=legacy,
                    evaluation_adequacy=row_bindings,
                ), job=job,
                row={"metrics": row["metrics"], "model_version": "1"},
                model_type=spec.model_type.value, x_uri=refs[spec.x_ref]["uri"],
                y_uri=refs["y"]["uri"], info=info,
                contract_uri=refs["contract"]["uri"], contract=contract,
                service=service,
            )
            return {
                "can_id": can_id,
                "passport_ref": publication.ref.model_dump(mode="json"),
            }

        records.append(context.effect(
            f"issue-passport:{job.id}@v1", inputs, publish, publish,
        ))
    return _passport_result(records)


def run_conformance(
    context: Any, *, passport_refs: list[dict[str, Any]], invoker: Any,
    service: ModelPassportService,
) -> dict[str, Any]:
    """Generate stored evidence receipts with legacy pointer integrity checks."""
    records = []
    for value in passport_refs:
        ref = ModelPassportRef.model_validate(value)
        candidate = service.get(ref)
        pointers = verify_evaluation_pointers(invoker, candidate.evaluation_pointers)
        inputs = {
            "passport_ref": ref.model_dump(mode="json"),
            "evaluation_pointers": [item.model_dump(mode="json") for item in pointers],
        }

        def collect(effect_id: str) -> dict[str, Any]:
            observed = service.generate_conformance(ref, effect_id=effect_id)
            if observed.evaluation_pointers not in ((), pointers):
                raise ValueError("conformance evidence changed verified Evals pointers")
            evidence = ConformanceEvidence.model_validate({
                **observed.model_dump(mode="python"),
                "evaluation_pointers": pointers,
            })
            return {
                "passport_ref": ref.model_dump(mode="json"),
                "conformance_evidence": evidence.model_dump(mode="json"),
            }

        output, receipt_ref = context.effect_with_ref(
            f"conformance:{ref.digest}@v1", inputs, collect, collect,
        )
        if output["passport_ref"] != ref.model_dump(mode="json"):
            raise ValueError("conformance receipt changed its passport reference")
        records.append({
            "can_id": _can_id(candidate),
            "passport_ref": ref.model_dump(mode="json"),
            "conformance_receipt_ref": receipt_ref.model_dump(mode="json"),
        })
    return {
        "can_ids": [item["can_id"] for item in records],
        "passport_refs": [item["passport_ref"] for item in records],
        "conformance_receipt_refs": [
            item["conformance_receipt_ref"] for item in records
        ],
        "receipts": records,
    }


def _training_parts(terminal: dict[str, Any]) -> tuple[dict[str, Any], list[dict]]:
    if terminal.get("status") != "completed":
        raise ValueError("passport issuance requires completed ML training")
    dataset, rows = terminal.get("dataset_terminal"), terminal.get("portfolio")
    if not isinstance(dataset, dict) or not isinstance(rows, list):
        raise ValueError("completed ML training terminal is incomplete")
    if not isinstance(dataset.get("vehicle_id"), str) or not isinstance(
        dataset.get("legacy_projection"), dict,
    ):
        raise ValueError("Dataset terminal lacks trusted CAN legacy projection")
    return dataset, rows


def _require_record_cases(records, rows) -> None:
    expected = tuple((str(row["can_id"]), str(row["job_id"])) for row in rows)
    for record in records:
        observed = tuple(
            (case.case_id, case.model_id) for case in record.adequacy.cases
        )
        if observed != expected:
            raise ValueError("verified Evals adequacy does not match training portfolio")


def _passport_context(terminal, root, pointers) -> CanPassportContext:
    bundle, artifacts = terminal["training_bundle"], terminal["artifacts"]
    roles = {
        "training_dataset": bundle["augmented_dataset"],
        "training_manifest": bundle["augmented_manifest"],
        "synthesis_dataset": artifacts["synthesize:dataset"],
        "synthesis_manifest": artifacts["synthesize:manifest"],
    }
    lineage = tuple(
        file_artifact_ref(role, ref["uri"], ref["sha256"])
        for role, ref in roles.items()
    )
    return CanPassportContext(
        lineage_artifacts=lineage, scenario_lineage=None, storage_root=str(root),
        evaluation_pointers=tuple(pointers),
    )


def _can_id(passport: Any) -> str:
    binding = passport.can_legacy_binding
    if binding is None:
        raise ValueError("lifecycle passport lacks a CAN legacy binding")
    return binding.can_id


def _passport_result(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "can_ids": [item["can_id"] for item in records],
        "passport_refs": [item["passport_ref"] for item in records],
        "passports": records,
    }


__all__ = ["issue_passports", "promote_passports", "run_conformance"]
