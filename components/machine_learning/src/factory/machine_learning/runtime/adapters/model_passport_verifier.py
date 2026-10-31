"""Fail-closed verification of every external ModelPassport reference."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlparse

from ..model_passport import ModelPassport
from ..passport_artifacts import verify_artifact_ref

ToolInvoker = Callable[..., Any]


class LocalModelPassportVerifier:
    """Revalidate local bytes and Dataset-owned lineage through MCP."""

    def __init__(self, storage_root: str | Path, tool_invoker: ToolInvoker) -> None:
        self._passport_root = Path(storage_root).expanduser().absolute()
        self._invoker = tool_invoker

    def verify(self, passport: ModelPassport) -> None:
        """Raise when any claimed external identity cannot be re-derived."""
        lineage = {ref.role: ref for ref in passport.lineage_artifacts}
        scenarios: list[dict[str, Any] | None] = []
        dataset_root: Path | None = None
        for prefix in ("training", "synthesis"):
            dataset = lineage[f"{prefix}_dataset"]
            manifest = lineage[f"{prefix}_manifest"]
            root = _dataset_root(dataset.uri, manifest.uri)
            if dataset_root is not None and root != dataset_root:
                raise ValueError("passport Dataset lineage spans multiple storage roots")
            dataset_root = root
            verify_artifact_ref(dataset, root / "artifacts")
            verify_artifact_ref(manifest, root / "manifests")
            resolved = self._call(
                "dataset_resolve_artifact",
                dataset_uri=dataset.uri,
                storage_root=str(root),
            )
            if (
                resolved.get("dataset_uri") != dataset.uri
                or resolved.get("manifest_uri") != manifest.uri
                or resolved.get("dataset_digest") != dataset.digest
            ):
                raise ValueError(f"{prefix} Dataset manifest disagrees with passport")
            scenarios.append(resolved.get("scenario_lineage"))
        if dataset_root is None:
            raise ValueError("passport has no Dataset lineage storage root")
        self._verify_scenario(passport, scenarios, dataset_root)
        refs = [
            passport.preparation.x,
            passport.preparation.y,
            passport.preparation.feature_contract,
            *([passport.preparation.timespans] if passport.preparation.timespans else []),
            passport.model_artifact,
            *(item.evidence for item in passport.conformance_evidence),
        ]
        for ref in refs:
            verify_artifact_ref(ref, self._passport_root)

    def _verify_scenario(
        self, passport: ModelPassport, values: list[dict[str, Any] | None],
        dataset_root: Path,
    ) -> None:
        declared = passport.scenario_lineage
        if declared is None:
            if any(value is not None for value in values):
                raise ValueError("Dataset ScenarioPack lineage is missing from passport")
            return
        expected = {
            "identity": declared.identity, "version": declared.version,
            "uri": declared.uri, "digest": declared.digest,
        }
        for value in values:
            if not isinstance(value, dict) or value.get("scenario_pack") != expected:
                raise ValueError("Dataset ScenarioPack lineage disagrees with passport")
            if (
                value.get("generator_adapter") != declared.generator_adapter
                or value.get("generator_version") != declared.generator_version
                or value.get("seed") != declared.seed
            ):
                raise ValueError("Dataset scenario generation binding disagrees with passport")
        pack = self._call(
            "dataset_get_scenario_pack", **expected, storage_root=str(dataset_root),
        )
        if any(pack.get(key) != value for key, value in expected.items() if key != "uri"):
            raise ValueError("ScenarioPack retrieval disagrees with passport")

    def _call(self, tool_name: str, **kwargs: Any) -> dict[str, Any]:
        try:
            result = self._invoker(tool_name, **kwargs)
        except Exception as exc:
            raise ValueError(f"{tool_name} verification failed: {exc}") from exc
        if (
            not isinstance(result, dict)
            or result.get("schema_version") != "v1"
            or result.get("ok") is not True
            or not isinstance(result.get("data"), dict)
        ):
            raise ValueError(f"{tool_name} verification failed: {result}")
        return result["data"]


def _dataset_root(dataset_uri: str, manifest_uri: str) -> Path:
    manifest = _file_path(manifest_uri)
    if manifest.parent.name != "manifests":
        raise ValueError("passport Dataset manifest is not in a canonical store")
    root = manifest.parent.parent.expanduser().absolute()
    dataset = _file_path(dataset_uri).expanduser().absolute()
    try:
        dataset.relative_to(root / "artifacts")
    except ValueError as exc:
        raise ValueError("passport Dataset artifact is not in its manifest store") from exc
    return root


def _file_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme != "file" or not parsed.path.startswith("/"):
        raise ValueError("passport Dataset lineage must use absolute file URIs")
    return Path(unquote(parsed.path))


__all__ = ["LocalModelPassportVerifier"]
