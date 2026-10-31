"""Property and security coverage for approved DBC discovery and semantics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st
from pydantic import ValidationError

from factory.dataset.interface import (
    dbc_signal_identity, dbc_version_identity, dataset_resolve_dbc_candidate,
)
from factory.dataset.runtime.adapters.dbc_catalog import LocalDbcCatalog
from factory.dataset.runtime.dbc_models import DbcCatalogEntry, MessageFingerprint
from factory.dataset.runtime.dbc_parser import parse_dbc_definition
from factory.dataset.runtime.dbc_resolver import rank_dbc_candidates

from .can_intelligence_fixtures import write_catalog


def _entries(tmp_path: Path) -> tuple[DbcCatalogEntry, ...]:
    _, raw = write_catalog(tmp_path)
    first = DbcCatalogEntry.model_validate(raw)
    second = DbcCatalogEntry.model_validate({
        **first.model_dump(mode="json"), "catalog_id": "other-can",
        "vehicle": {"aliases": ("other-car",), "make": "", "model": "", "years": ()},
    })
    return first, second


@given(order=st.permutations((0, 1)))
@settings(max_examples=10, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_ranking_is_permutation_invariant(tmp_path: Path, order: list[int]) -> None:
    entries = _entries(tmp_path)
    result = rank_dbc_candidates(tuple(entries[index] for index in order),
                                 vehicle_alias="fixture car")
    assert result.status == "resolved"
    assert result.selected and result.selected.catalog_id == "fixture-can"
    assert [item.catalog_id for item in result.candidates] == ["fixture-can", "other-can"]


def test_tie_and_below_threshold_are_ambiguous(tmp_path: Path) -> None:
    entries = _entries(tmp_path)
    tied = rank_dbc_candidates(entries, fingerprints=(
        MessageFingerprint(arbitration_id=256, dlc=8),
    ))
    assert tied.status == "ambiguous" and "tied" in tied.errors[0]
    below = rank_dbc_candidates(entries, vehicle_alias="fixture-car", threshold=100)
    assert below.status == "ambiguous" and "below" in below.errors[0]


def test_catalog_rejects_digest_mismatch_and_symlink(tmp_path: Path) -> None:
    dbc, _ = write_catalog(tmp_path)
    catalog = LocalDbcCatalog(tmp_path)
    entry = catalog.list_entries()[0]
    dbc.write_text("tampered")
    with pytest.raises(ValueError, match="digest mismatch"):
        catalog.verified_path(entry)
    dbc.unlink()
    target = dbc.parent / "outside-target.dbc"
    target.write_text("outside")
    dbc.symlink_to(target)
    with pytest.raises(ValueError, match="symlinked"):
        catalog.verified_path(entry)


def test_catalog_rejects_artifact_outside_root(tmp_path: Path) -> None:
    _, raw = write_catalog(tmp_path)
    outside = tmp_path / "outside.dbc"
    outside.write_text("outside")
    raw["provenance"]["artifact_uri"] = outside.resolve().as_uri()
    raw["provenance"]["sha256"] = hashlib.sha256(outside.read_bytes()).hexdigest()
    entry = DbcCatalogEntry.model_validate(raw)
    with pytest.raises(ValueError, match="escapes"):
        LocalDbcCatalog(tmp_path).verified_path(entry)


def test_parser_and_identity_are_deterministic(tmp_path: Path) -> None:
    dbc, _ = write_catalog(tmp_path)
    catalog = LocalDbcCatalog(tmp_path)
    entry = catalog.list_entries()[0]
    first = parse_dbc_definition(dbc, entry.provenance,
                                 catalog_id=entry.catalog_id, version=entry.version)
    second = parse_dbc_definition(dbc, entry.provenance,
                                  catalog_id=entry.catalog_id, version=entry.version)
    assert first == second
    assert first.definition_id == dbc_version_identity(entry.provenance.sha256)
    engine = first.messages[0]
    assert engine.signals[0].signal_id == dbc_signal_identity(
        first.digest, engine.arbitration_id, engine.signals[0].name,
    )


def test_resolve_without_explicit_path_returns_definition(tmp_path: Path) -> None:
    write_catalog(tmp_path)
    result = dataset_resolve_dbc_candidate(tmp_path, vehicle_alias="fixture-car")
    assert result["status"] == "resolved"
    assert result["selected"]["catalog_id"] == "fixture-can"
    assert result["definition"]["messages"]


def test_unapproved_license_and_parser_mismatch_fail_closed(tmp_path: Path) -> None:
    _, raw = write_catalog(tmp_path)
    unapproved = dataset_resolve_dbc_candidate(
        tmp_path, catalog_id="not-approved", version="1.0.0",
    )
    assert unapproved["status"] == "not_found"
    invalid_license = {**raw, "provenance": {
        **raw["provenance"], "spdx_license": "NOASSERTION",
    }}
    with pytest.raises(ValidationError, match="SPDX"):
        DbcCatalogEntry.model_validate(invalid_license)
    raw["provenance"]["parser_version"] = "0.0.0"
    manifest = tmp_path / "dbc_catalog" / "manifest.json"
    manifest.write_text(json.dumps({"entries": [raw]}))
    mismatch = dataset_resolve_dbc_candidate(
        tmp_path, catalog_id="fixture-can", version="1.0.0",
    )
    assert mismatch["status"] == "not_found"
    assert "parser identity/version mismatch" in mismatch["errors"][0]


def test_exact_typed_vehicle_fields_contribute_to_ranking(tmp_path: Path) -> None:
    result = rank_dbc_candidates(
        _entries(tmp_path), vehicle_make=" fixture ", vehicle_model="CAR",
        vehicle_year=2026,
    )
    assert result.status == "resolved"
    assert result.selected and result.selected.catalog_id == "fixture-can"
    assert result.candidates[0].score == 80
    assert result.candidates[0].explanation == (
        "vehicle make matched exactly:  fixture ",
        "vehicle model matched exactly: CAR",
        "vehicle year matched exactly: 2026",
    )


def test_unverified_candidate_cannot_influence_ranking(tmp_path: Path) -> None:
    _, raw = write_catalog(tmp_path)
    tampered = {
        **raw, "catalog_id": "tampered-preferred",
        "vehicle": {"make": "Other", "model": "Other", "years": [],
                    "aliases": ["preferred"]},
        "provenance": {**raw["provenance"], "sha256": "0" * 64},
    }
    manifest = tmp_path / "dbc_catalog" / "manifest.json"
    manifest.write_text(json.dumps({"entries": [raw, tampered]}))
    result = dataset_resolve_dbc_candidate(
        tmp_path, vehicle_alias="preferred", vehicle_make="Fixture",
    )
    assert result["status"] == "resolved"
    assert result["selected"]["catalog_id"] == "fixture-can"
    assert [item["catalog_id"] for item in result["candidates"]] == ["fixture-can"]
