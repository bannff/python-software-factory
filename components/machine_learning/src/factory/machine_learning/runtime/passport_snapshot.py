"""Private verified snapshots for exact passport-bound artifact loading."""
from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote, urlparse

from .model_passport import ModelPassport
from .passport_refs import PassportArtifactRef
from .passport_snapshot_io import copy_verified_artifact
from .passport_tree_seal import remove_staging_tree

_TREE_FORMATS = frozenset({
    "mlflow-lightgbm", "transformers-patchtst", "mlx-safetensors",
    "chronos2-native-probe", "chronos2-backbone",
})


@contextmanager
def verified_snapshot(
    passport: ModelPassport, storage_root: str | Path, roles: tuple[str, ...],
) -> Iterator[dict[str, Path]]:
    """Copy exact bound artifacts into one exclusive private directory."""
    root = Path(storage_root).expanduser().absolute()
    base = root / ".verified_snapshots"
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    directory = Path(tempfile.mkdtemp(prefix="passport-", dir=base))
    os.chmod(directory, 0o700)
    refs = _references(passport)
    paths: dict[str, Path] = {"root": directory}
    try:
        for role in roles:
            ref = refs[role]
            source = _file_path(ref.uri)
            destination = (
                directory / role if ref.format in _TREE_FORMATS
                else directory / f"{role}{source.suffix}"
            )
            copy_verified_artifact(ref, root, destination)
            paths[role] = destination
        yield paths
    finally:
        remove_staging_tree(directory)


def _references(passport: ModelPassport) -> dict[str, PassportArtifactRef]:
    references = {
        "model": passport.model_artifact,
        "feature_contract": passport.preparation.feature_contract,
        "prepared_x": passport.preparation.x,
        "prepared_y": passport.preparation.y,
    }
    if passport.preparation.timespans is not None:
        references["prepared_timespans"] = passport.preparation.timespans
    return references


def _file_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError("ModelPassport snapshots require file URIs")
    return Path(unquote(parsed.path))


__all__ = ["copy_verified_artifact", "verified_snapshot"]
