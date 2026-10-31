"""Deterministic, explainable DBC ranking and verified resolution."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.metadata import version as package_version
from pathlib import Path

from .atomic_io import read_bytes_no_follow
from .dbc_models import (
    DbcArtifactProvenance, DbcCandidateScore, DbcCatalogEntry, DbcResolution,
    MessageFingerprint,
)
from .dbc_parser import parse_dbc_definition
from .dbc_semantics import DbcVersionDefinition
from .ports import DbcCatalogPort

@dataclass(frozen=True)
class ResolvedDbc:
    path: Path
    provenance: DbcArtifactProvenance
    definition: DbcVersionDefinition
    resolution: DbcResolution

def rank_dbc_candidates(
    entries: tuple[DbcCatalogEntry, ...], *, vehicle_alias: str = "",
    vehicle_make: str = "", vehicle_model: str = "", vehicle_year: int | None = None,
    fingerprints: tuple[MessageFingerprint, ...] = (), threshold: int = 10,
) -> DbcResolution:
    alias = _normalize(vehicle_alias)
    make = _exact(vehicle_make)
    model = _exact(vehicle_model)
    wanted = set(fingerprints)
    ranked: list[tuple[DbcCandidateScore, DbcCatalogEntry]] = []
    for entry in entries:
        aliases = {_normalize(value) for value in entry.vehicle.aliases}
        alias_hits = (vehicle_alias,) if alias and alias in aliases else ()
        make_hit = bool(make and make == _exact(entry.vehicle.make))
        model_hit = bool(model and model == _exact(entry.vehicle.model))
        year_hit = bool(vehicle_year is not None and vehicle_year in entry.vehicle.years)
        fingerprint_hits = tuple(sorted(wanted.intersection(entry.message_fingerprints), key=lambda item: (
            item.arbitration_id, item.dlc, item.is_extended,
        )))
        score = (
            (50 * len(alias_hits)) + (25 if make_hit else 0)
            + (35 if model_hit else 0) + (20 if year_hit else 0)
            + (10 * len(fingerprint_hits))
        )
        reasons = tuple(filter(None, (
            f"vehicle alias matched exactly: {vehicle_alias}" if alias_hits else "",
            f"vehicle make matched exactly: {vehicle_make}" if make_hit else "",
            f"vehicle model matched exactly: {vehicle_model}" if model_hit else "",
            f"vehicle year matched exactly: {vehicle_year}" if year_hit else "",
            f"observed message fingerprints matched: {len(fingerprint_hits)}/{len(wanted)}" if wanted else "",
        )))
        ranked.append((DbcCandidateScore(
            catalog_id=entry.catalog_id, version=entry.version,
            artifact_sha256=entry.provenance.sha256, score=score,
            matched_aliases=alias_hits, matched_fingerprints=fingerprint_hits,
            explanation=reasons or ("no normalized metadata matched",),
        ), entry))
    ranked.sort(key=lambda pair: (
        -pair[0].score, pair[0].catalog_id, pair[0].version, pair[0].artifact_sha256,
    ))
    candidates = tuple(pair[0] for pair in ranked)
    if not ranked:
        return DbcResolution(status="not_found", candidates=(), threshold=threshold,
                             errors=("approved DBC catalog is empty",))
    top_score = ranked[0][0].score
    tied = sum(item[0].score == top_score for item in ranked) > 1
    if top_score < threshold or tied:
        reason = "top candidates tied" if tied else "top candidate is below threshold"
        return DbcResolution(status="ambiguous", candidates=candidates,
                             threshold=threshold, errors=(reason,))
    return DbcResolution(status="resolved", selected=ranked[0][1],
                         candidates=candidates, threshold=threshold)

def verified_catalog_entries(catalog: DbcCatalogPort) -> tuple[DbcCatalogEntry, ...]:
    """Return only entries whose local immutable artifact verifies now."""
    verified: list[DbcCatalogEntry] = []
    for entry in catalog.list_entries():
        try:
            catalog.verified_path(entry)
        except ValueError:
            continue
        verified.append(entry)
    return tuple(verified)

def resolve_catalog_dbc(
    catalog: DbcCatalogPort, *, catalog_id: str = "", version: str = "",
    vehicle_alias: str = "", vehicle_make: str = "", vehicle_model: str = "",
    vehicle_year: int | None = None,
    fingerprints: tuple[MessageFingerprint, ...] = (), threshold: int = 10,
) -> ResolvedDbc:
    if catalog_id:
        selected = catalog.get_entry(catalog_id, version)
        if selected is None:
            raise ValueError("explicit DBC candidate is not approved")
        resolution = DbcResolution(status="resolved", selected=selected, threshold=threshold,
                                   candidates=(_score_explicit(selected),))
    else:
        resolution = rank_dbc_candidates(
            verified_catalog_entries(catalog), vehicle_alias=vehicle_alias,
            vehicle_make=vehicle_make, vehicle_model=vehicle_model,
            vehicle_year=vehicle_year, fingerprints=fingerprints, threshold=threshold,
        )
        if resolution.status != "resolved" or resolution.selected is None:
            raise ValueError(f"DBC resolution {resolution.status}: {', '.join(resolution.errors)}")
        selected = resolution.selected
    path = catalog.verified_path(selected)
    _verify_parser(selected.provenance)
    definition = parse_dbc_definition(
        path, selected.provenance, catalog_id=selected.catalog_id, version=selected.version,
    )
    return ResolvedDbc(path, selected.provenance, definition, resolution)

def reverify_bound_dbc(path: Path, raw_definition: dict) -> ResolvedDbc:
    """Rebind trusted catalog metadata only after verifying exact execution bytes."""
    definition = DbcVersionDefinition.model_validate(raw_definition)
    content = read_bytes_no_follow(path)
    observed = hashlib.sha256(content).hexdigest()
    if observed != definition.digest or observed != definition.provenance.sha256:
        raise ValueError("bound DBC definition digest mismatch")
    _verify_parser(definition.provenance)
    parsed = parse_dbc_definition(
        path, definition.provenance, catalog_id=definition.catalog_id,
        version=definition.version,
    )
    if parsed != definition:
        raise ValueError("bound DBC definition does not match verified execution bytes")
    entry = DbcCatalogEntry(
        catalog_id=definition.catalog_id, version=definition.version,
        provenance=definition.provenance,
        vehicle={"aliases": (definition.catalog_id,)},
        message_fingerprints=tuple(
            {MessageFingerprint(arbitration_id=message.arbitration_id,
                                dlc=message.dlc, is_extended=message.is_extended)
             for message in definition.messages}
        ),
    )
    resolution = DbcResolution(
        status="resolved", selected=entry, threshold=0,
        candidates=(_score_explicit(entry),),
    )
    return ResolvedDbc(path.resolve(), definition.provenance, parsed, resolution)

def resolve_explicit_dbc(path: Path) -> ResolvedDbc:
    if path.is_symlink() or not path.is_file():
        raise ValueError("explicit DBC path must be a regular non-symlink file")
    content = read_bytes_no_follow(path)
    sha256 = hashlib.sha256(content).hexdigest()
    parser_version = package_version("cantools")
    provenance = DbcArtifactProvenance(
        source_url=path.resolve().as_uri(), artifact_uri=path.resolve().as_uri(),
        source_kind="explicit_local", spdx_license="NOASSERTION",
        retrieved_at="1970-01-01T00:00:00Z", sha256=sha256,
        parser_name="cantools", parser_version=parser_version,
        validation_status="validated",
    )
    definition = parse_dbc_definition(
        path.resolve(), provenance, catalog_id=f"explicit-{sha256[:16]}", version="local",
    )
    entry = DbcCatalogEntry(
        catalog_id=definition.catalog_id, version=definition.version,
        provenance=provenance,
        vehicle={"aliases": ("explicit-local",)},
        message_fingerprints=tuple(
            {MessageFingerprint(arbitration_id=message.arbitration_id,
                                dlc=message.dlc, is_extended=message.is_extended)
             for message in definition.messages}
        ),
    )
    resolution = DbcResolution(status="resolved", selected=entry,
                               candidates=(_score_explicit(entry),), threshold=0)
    return ResolvedDbc(path.resolve(), provenance, definition, resolution)

def _score_explicit(entry: DbcCatalogEntry) -> DbcCandidateScore:
    return DbcCandidateScore(catalog_id=entry.catalog_id, version=entry.version,
        artifact_sha256=entry.provenance.sha256, score=100,
        explanation=("explicit approved candidate",))

def _verify_parser(provenance: DbcArtifactProvenance) -> None:
    if provenance.parser_name != "cantools" or provenance.parser_version != package_version("cantools"):
        raise ValueError("approved DBC parser identity/version mismatch")

def _exact(value: str) -> str:
    return " ".join(value.casefold().split())

def _normalize(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())

__all__ = [
    "ResolvedDbc", "rank_dbc_candidates", "resolve_catalog_dbc",
    "resolve_explicit_dbc", "reverify_bound_dbc", "verified_catalog_entries",
]
