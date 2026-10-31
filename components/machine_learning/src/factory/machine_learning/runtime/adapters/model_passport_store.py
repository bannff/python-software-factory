"""Content-addressed local ModelPassport registry."""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from ..model_passport import ModelPassport
from ..passport_codec import load_model_passport, passport_artifact_bytes
from ..passport_paths import reject_symlink_ancestors
from ..passport_store_models import (
    ModelPassportConflictError, ModelPassportIntegrityError,
    ModelPassportPublication, ModelPassportRef, ModelPassportRevisionError,
)
from ..passport_validation import canonical_json


class LocalModelPassportStore:
    """Write-once objects plus exact immutable logical-key references."""

    def __init__(self, storage_root: str | Path) -> None:
        self._root = Path(storage_root).expanduser().absolute()
        try:
            reject_symlink_ancestors(self._root)
        except ValueError as exc:
            raise ModelPassportIntegrityError(str(exc)) from exc
        self._base = self._root / "model_passports"
        self._ensure_directory(self._base / "objects")
        self._ensure_directory(self._base / "index")

    def publish(self, passport: ModelPassport) -> ModelPassportPublication:
        value = load_model_passport(passport)
        content = passport_artifact_bytes(value)
        ref_path = self._ref_path(
            value.model_id, value.model_version, value.passport_revision,
        )
        if ref_path.exists() or ref_path.is_symlink():
            return self._existing(ref_path, content)
        self._verify_predecessor(value)
        object_path = self._object_path(value.passport_digest)
        self._write_object(object_path, content)
        ref = ModelPassportRef(
            model_id=value.model_id, model_version=value.model_version,
            passport_revision=value.passport_revision,
            uri=object_path.absolute().as_uri(), digest=value.passport_digest,
        )
        if not self._install_exclusive(
            ref_path, canonical_json(ref.model_dump(mode="json")),
        ):
            return self._existing(ref_path, content)
        return ModelPassportPublication(status="published", ref=ref)

    def get(self, ref: ModelPassportRef) -> ModelPassport:
        stored_ref = self._read_ref(self._ref_path(
            ref.model_id, ref.model_version, ref.passport_revision,
        ))
        if stored_ref != ref:
            raise ModelPassportIntegrityError("passport reference is stale or not registered")
        return self._load_object(stored_ref)

    def get_by_model(
        self, model_id: str, model_version: str, passport_revision: int,
    ) -> ModelPassport:
        ref = self._read_ref(self._ref_path(model_id, model_version, passport_revision))
        return self._load_object(ref)

    def _existing(self, ref_path: Path, content: bytes) -> ModelPassportPublication:
        existing_ref = self._read_ref(ref_path)
        existing = self.get(existing_ref)
        if passport_artifact_bytes(existing) == content:
            return ModelPassportPublication(status="existing", ref=existing_ref)
        raise ModelPassportConflictError(
            "model passport logical key already has different content"
        )

    def _verify_predecessor(self, passport: ModelPassport) -> None:
        if passport.passport_revision == 1:
            return
        try:
            prior = self.get_by_model(
                passport.model_id, passport.model_version,
                passport.passport_revision - 1,
            )
        except KeyError as exc:
            raise ModelPassportRevisionError("passport revision gap is not allowed") from exc
        prior_ref = self._read_ref(self._ref_path(
            prior.model_id, prior.model_version, prior.passport_revision,
        ))
        predecessor = passport.predecessor
        if predecessor is None or predecessor.model_dump() != prior_ref.model_dump():
            raise ModelPassportRevisionError(
                "passport predecessor does not match the exact registered prior revision"
            )

    def _load_object(self, ref: ModelPassportRef) -> ModelPassport:
        expected = self._object_path(ref.digest)
        actual = self._path_from_uri(ref.uri)
        if actual != expected:
            raise ModelPassportIntegrityError("passport reference points to a stale object")
        self._guard(actual)
        if not actual.exists() or actual.is_symlink():
            raise ModelPassportIntegrityError("passport object is missing or is a symlink")
        try:
            passport = load_model_passport(actual.read_bytes())
        except ValueError as exc:
            raise ModelPassportIntegrityError(str(exc)) from exc
        if (
            passport.model_id != ref.model_id
            or passport.model_version != ref.model_version
            or passport.passport_revision != ref.passport_revision
            or passport.passport_digest != ref.digest
        ):
            raise ModelPassportIntegrityError("passport object does not match its index")
        return passport

    def _read_ref(self, path: Path) -> ModelPassportRef:
        self._guard(path)
        if not path.exists() or path.is_symlink():
            raise KeyError("model passport revision not found")
        raw = path.read_bytes()
        try:
            ref = ModelPassportRef.model_validate_json(raw)
        except Exception as exc:
            raise ModelPassportIntegrityError("passport index reference is invalid") from exc
        if raw != canonical_json(ref.model_dump(mode="json")):
            raise ModelPassportIntegrityError("passport index reference is not canonical")
        return ref

    def _write_object(self, path: Path, content: bytes) -> None:
        if self._install_exclusive(path, content):
            return
        self._guard(path)
        if path.is_symlink() or path.read_bytes() != content:
            raise ModelPassportIntegrityError("immutable passport object already differs")

    def _install_exclusive(self, path: Path, content: bytes) -> bool:
        """Atomically link fully-written bytes only when ``path`` is absent."""
        self._ensure_directory(path.parent)
        self._guard(path)
        descriptor, temp_name = tempfile.mkstemp(prefix=".passport-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_name, 0o444)
            try:
                os.link(temp_name, path)
            except FileExistsError:
                return False
            return True
        finally:
            Path(temp_name).unlink(missing_ok=True)

    def _object_path(self, digest: str) -> Path:
        return self._base / "objects" / f"{digest}.json"

    def _ref_path(self, model_id: str, model_version: str, revision: int) -> Path:
        identity = hashlib.sha256(model_id.encode()).hexdigest()
        version = hashlib.sha256(model_version.encode()).hexdigest()
        return self._base / "index" / identity / version / f"{revision}.ref.json"

    def _path_from_uri(self, uri: str) -> Path:
        from urllib.parse import unquote, urlparse
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            raise ModelPassportIntegrityError("local passport references require file URIs")
        return Path(unquote(parsed.path)).absolute()

    def _ensure_directory(self, path: Path) -> None:
        self._guard(path)
        path.mkdir(parents=True, exist_ok=True)
        self._guard(path)

    def _guard(self, path: Path) -> None:
        try:
            reject_symlink_ancestors(self._root)
            reject_symlink_ancestors(path)
            path.absolute().relative_to(self._base.absolute())
            path.resolve(strict=False).relative_to(self._base.resolve(strict=False))
        except ValueError as exc:
            raise ModelPassportIntegrityError(
                "passport path escapes the storage root or contains symlinks"
            ) from exc


__all__ = ["LocalModelPassportStore"]
