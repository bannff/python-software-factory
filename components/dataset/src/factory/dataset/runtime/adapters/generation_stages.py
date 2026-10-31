"""Adapters for the native agentic-generation stage callables.

Stage logic was ported from bannff/Agentic-Datasets@26cb683 into
``factory.dataset.runtime.stages``. These adapters keep the strict recipe
configuration contract: allowed-key validation, backend resolution into a
bound ``CompletionPort``, APIGenMT tool-schema-snapshot enforcement, and
canonical record validation at both boundaries.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping
from importlib import import_module
from typing import Any

from ..contracts import DatasetFallbackRecord, DatasetToolSchemaSnapshotRef
from ..ports import CompletionPort
from ..validation import validate_conversation_records

NATIVE_STAGE_VERSION = "factory-native-1"
PORTED_FROM = "bannff/Agentic-Datasets@26cb683"

# Recipe keys resolved into a bound CompletionPort before stage dispatch.
_COMPLETION_KEYS = ("model", "temperature", "max_tokens", "num_retries")


class _GenerationStageAdapter:
    """Common completion binding and strict configuration behavior."""

    name: str
    stage_import: str
    allowed_config: frozenset[str]

    def __init__(
        self,
        stage_callable: Callable[..., Iterable[Any]] | None = None,
        completion_factory: Callable[..., CompletionPort] | None = None,
    ) -> None:
        self._stage_callable = stage_callable
        self._completion_factory = completion_factory
        self.fallback_record: DatasetFallbackRecord | None = None

    @property
    def stage_version(self) -> str:
        return NATIVE_STAGE_VERSION

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[Any]:
        values = dict(config or {})
        values = self._resolve_completion(values)
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(f"Unsupported {self.name} configuration: {sorted(unknown)}")
        self.fallback_record = self._build_fallback(values)
        stage = self._stage_callable or self._load_stage()
        validated_inputs = validate_conversation_records(records)
        return validate_conversation_records(stage(validated_inputs, **values))

    def _resolve_completion(self, values: dict[str, Any]) -> dict[str, Any]:
        """Bind recipe backend selection into a CompletionPort instance.

        Recipes specify ``backend`` plus optional ``model``/``temperature``/
        ``max_tokens``/``num_retries``. The adapter resolves these through the
        configured completion factory (``llm_gateway``-routed in production)
        and replaces them with a bound ``completion`` port.
        """
        # Reject raw completion objects in recipes; routing must go through llm_gateway.
        if "completion" in values:
            raise ValueError(
                f"{self.name} stage does not accept raw 'completion'; "
                "use 'backend' and optional 'model' instead"
            )
        if "backend" not in values:
            return values
        if self._completion_factory is None:
            raise ValueError(
                f"{self.name} stage received 'backend' but no completion factory is configured"
            )
        backend = values.pop("backend")
        overrides = {key: values.pop(key) for key in _COMPLETION_KEYS if key in values}
        values["completion"] = self._completion_factory(backend=backend, **overrides)
        return values

    def _build_fallback(self, values: dict[str, Any]) -> DatasetFallbackRecord | None:
        """Surface deterministic (use_llm=False) runs as typed fallback lineage."""
        if values.get("use_llm") is not False:
            return None
        completion = values.get("completion")
        requested = getattr(completion, "backend", None) or "llm"
        return DatasetFallbackRecord(
            requested_backend=requested,
            actual_backend="deterministic",
            reason=f"{self.name} stage executed with use_llm=False (deterministic templates)",
            degraded_quality=True,
            authorized=True,
        )

    def _load_stage(self) -> Callable[..., Iterable[Any]]:
        module_name, function_name = self.stage_import.rsplit(".", 1)
        try:
            stage = getattr(import_module(module_name), function_name)
        except (ImportError, AttributeError) as error:
            raise RuntimeError(
                f"Native dataset stage is unavailable: {self.stage_import}"
            ) from error
        return stage


class AgentInstructStageAdapter(_GenerationStageAdapter):
    """Adapter for ``factory.dataset.runtime.stages.agentinstruct``."""

    name = "agentinstruct"
    stage_import = "factory.dataset.runtime.stages.agentinstruct.agentinstruct"
    allowed_config = frozenset({
        "k_variants", "transforms", "complexity_levels", "dedupe", "use_llm", "completion",
        "backend", "model", "temperature", "max_tokens", "num_retries",
    })


class S2MStageAdapter(_GenerationStageAdapter):
    """Adapter for ``factory.dataset.runtime.stages.s2m``."""

    name = "s2m"
    stage_import = "factory.dataset.runtime.stages.s2m.s2m"
    allowed_config = frozenset({
        "min_turns", "max_turns", "use_llm", "completion",
        "backend", "model", "temperature", "max_tokens", "num_retries",
    })


class APIGenMTStageAdapter(_GenerationStageAdapter):
    """Adapter for ``factory.dataset.runtime.stages.apigenmt``."""

    name = "apigenmt"
    stage_import = "factory.dataset.runtime.stages.apigenmt.apigenmt"
    allowed_config = frozenset({
        "tools", "max_tools_per_conversation", "use_llm", "generate_responses", "completion",
        "backend", "model", "temperature", "max_tokens", "num_retries",
    })

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[Any]:
        values = dict(config or {})
        tool_snapshot = values.pop("tool_schema_snapshot", None)
        if isinstance(tool_snapshot, Mapping):
            tool_snapshot = DatasetToolSchemaSnapshotRef.model_validate(tool_snapshot)
        if not isinstance(tool_snapshot, DatasetToolSchemaSnapshotRef):
            raise ValueError("APIGenMT requires an immutable tool schema snapshot")

        tool_definitions = values.get("tools")
        if tool_definitions is not None:
            normalized_tools = list(tool_definitions)
            tool_names: list[str] = []
            for tool in normalized_tools:
                if not isinstance(tool, Mapping) or "name" not in tool:
                    raise ValueError("APIGenMT tool entries must include names")
                name = str(tool["name"]).strip()
                if not name:
                    raise ValueError("APIGenMT tool entries must include names")
                tool_names.append(name)
            disallowed = sorted(set(tool_names) - set(tool_snapshot.allowed_tools))
            if disallowed:
                raise ValueError(
                    f"APIGenMT tool schema snapshot does not allow tools: {disallowed}"
                )
            values["tools"] = normalized_tools

        return super().execute(records, values)


class ReviewInstructStageAdapter(_GenerationStageAdapter):
    """Adapter for ``factory.dataset.runtime.stages.reviewinstruct``."""

    name = "reviewinstruct"
    stage_import = "factory.dataset.runtime.stages.reviewinstruct.reviewinstruct"
    allowed_config = frozenset({
        "accept_threshold", "max_iterations", "use_llm", "completion",
        "backend", "model", "temperature", "max_tokens", "num_retries",
    })
