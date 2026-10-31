"""Immutable local ScenarioPack storage adapter."""
from __future__ import annotations

import os
from pathlib import Path

from ..scenario_codec import (
    build_scenario_pack, canonical_json, parse_scenario_pack, scenario_pack_bytes,
)
from ..scenario_errors import ScenarioPackIntegrityError
from ..scenario_models import (
    ScenarioPack, ScenarioPackConflict, ScenarioPackDraft, ScenarioPackPublishResult,
    ScenarioPackRef,
)


class LocalScenarioPackStore:
    """Content-addressed pack store with an immutable identity/version index."""

    def __init__(self, storage_root: Path, *, create: bool = True) -> None:
        self.root = storage_root.resolve() / "scenario_packs"
        self.pack_dir = self.root / "sha256"
        self.identity_dir = self.root / "identities"
        if create:
            self.pack_dir.mkdir(parents=True, exist_ok=True)
            self.identity_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, draft: ScenarioPackDraft) -> ScenarioPackPublishResult:
        pack = build_scenario_pack(draft)
        pack_path = self.pack_dir / f"{pack.digest}.json"
        requested = ScenarioPackRef(
            identity=pack.identity, version=pack.version,
            uri=pack_path.resolve().as_uri(), digest=pack.digest,
        )
        existing = self._identity_ref(pack.identity, pack.version)
        if existing is not None:
            return self._existing_result(existing, requested)
        self._write_exclusive(pack_path, scenario_pack_bytes(pack))
        index_path = self._identity_path(pack.identity, pack.version)
        try:
            created = self._write_exclusive(
                index_path, canonical_json(requested.model_dump(mode="json")),
            )
        except FileExistsError:
            created = False
        if not created:
            return self._existing_result(self._read_ref(index_path), requested)
        self.load(requested)
        return ScenarioPackPublishResult(status="published", ref=requested)

    def load(self, ref: ScenarioPackRef) -> ScenarioPack:
        path = self._checked_pack_path(ref)
        if not path.exists():
            raise ScenarioPackIntegrityError("ScenarioPack artifact is missing")
        try:
            pack = parse_scenario_pack(path.read_bytes())
        except (OSError, ValueError) as error:
            raise ScenarioPackIntegrityError("ScenarioPack artifact failed verification") from error
        if (pack.identity, pack.version, pack.digest) != (
            ref.identity, ref.version, ref.digest,
        ):
            raise ScenarioPackIntegrityError(
                "ScenarioPack reference identity/version/digest mismatch"
            )
        return pack

    def _identity_ref(self, identity: str, version: str) -> ScenarioPackRef | None:
        path = self._identity_path(identity, version)
        return self._read_ref(path) if path.exists() else None

    def _existing_result(
        self, existing: ScenarioPackRef, requested: ScenarioPackRef,
    ) -> ScenarioPackPublishResult:
        self.load(existing)
        if existing.digest != requested.digest:
            return ScenarioPackPublishResult(status="conflict", conflict=ScenarioPackConflict(
                identity=requested.identity, version=requested.version,
                existing_digest=existing.digest, requested_digest=requested.digest,
            ))
        return ScenarioPackPublishResult(status="existing", ref=existing)

    def _checked_pack_path(self, ref: ScenarioPackRef) -> Path:
        from ..recipe import path_from_uri
        try:
            path = path_from_uri(ref.uri)
        except ValueError as error:
            raise ScenarioPackIntegrityError("ScenarioPack URI is invalid") from error
        expected = (self.pack_dir / f"{ref.digest}.json").resolve()
        if path != expected:
            raise ScenarioPackIntegrityError(
                "ScenarioPack URI is outside its content-addressed store"
            )
        return path

    def _identity_path(self, identity: str, version: str) -> Path:
        return self.identity_dir / f"{identity}@{version}.ref.json"

    @staticmethod
    def _read_ref(path: Path) -> ScenarioPackRef:
        try:
            content = path.read_bytes()
            ref = ScenarioPackRef.model_validate_json(content)
        except (OSError, ValueError) as error:
            raise ScenarioPackIntegrityError(
                "ScenarioPack identity reference failed verification"
            ) from error
        if canonical_json(ref.model_dump(mode="json")) != content:
            raise ScenarioPackIntegrityError(
                "ScenarioPack identity reference is not canonical"
            )
        return ref

    @staticmethod
    def _write_exclusive(path: Path, content: bytes) -> bool:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
        except FileExistsError:
            if path.read_bytes() != content:
                raise
            return False
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        return True
