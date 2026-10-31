"""Bounded YAML parsing used only by Permissions authoring operations."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from yaml.events import AliasEvent, DocumentStartEvent, ScalarEvent
from yaml.nodes import MappingNode, SequenceNode

from factory.mcp_utils.interface import is_bounded_json

MAX_YAML_BYTES = 65_536
_MAX_EVENTS = 4_096
_MAX_NODES = 4_096
_MAX_DEPTH = 12
_MAX_MAPPING_KEYS = 256
_MAX_SEQUENCE_ITEMS = 1_024


class PolicyYamlError(ValueError):
    """Stable, non-sensitive parser failure."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _text(value: str | bytes) -> str:
    if isinstance(value, str):
        raw = value.encode("utf-8")
    elif isinstance(value, bytes):
        raw = value
    else:
        raise PolicyYamlError("yaml_input_type")
    if len(raw) > MAX_YAML_BYTES:
        raise PolicyYamlError("policy_size_exceeded")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PolicyYamlError("yaml_encoding_error") from exc


def _scan(text: str) -> None:
    documents = 0
    events = 0
    try:
        for event in yaml.parse(text, Loader=yaml.SafeLoader):
            events += 1
            if events > _MAX_EVENTS:
                raise PolicyYamlError("yaml_budget_exceeded")
            if isinstance(event, DocumentStartEvent):
                documents += 1
                if documents > 1:
                    raise PolicyYamlError("yaml_document_count")
            if isinstance(event, AliasEvent) or getattr(event, "anchor", None) is not None:
                raise PolicyYamlError("yaml_alias_not_allowed")
            if isinstance(event, ScalarEvent) and event.value == "<<":
                raise PolicyYamlError("yaml_merge_not_allowed")
    except PolicyYamlError:
        raise
    except yaml.YAMLError as exc:
        raise PolicyYamlError("yaml_parse_error") from exc


def _walk(node: Any, depth: int, state: dict[str, int]) -> None:
    if depth > _MAX_DEPTH:
        raise PolicyYamlError("yaml_depth_exceeded")
    state["nodes"] += 1
    if state["nodes"] > _MAX_NODES:
        raise PolicyYamlError("yaml_budget_exceeded")
    if isinstance(node, MappingNode):
        if len(node.value) > _MAX_MAPPING_KEYS:
            raise PolicyYamlError("yaml_mapping_too_large")
        for key, value in node.value:
            _walk(key, depth + 1, state)
            _walk(value, depth + 1, state)
    elif isinstance(node, SequenceNode):
        if len(node.value) > _MAX_SEQUENCE_ITEMS:
            raise PolicyYamlError("yaml_sequence_too_large")
        for value in node.value:
            _walk(value, depth + 1, state)


def load_bounded_policy(value: str | bytes | dict[str, Any]) -> object:
    """Parse one UTF-8 YAML document under explicit complexity budgets."""
    if isinstance(value, dict):
        if not is_bounded_json(value):
            raise PolicyYamlError("policy_bounded_json")
        return value
    text = _text(value)
    _scan(text)
    try:
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        if node is not None:
            _walk(node, 0, {"nodes": 0})
        parsed = yaml.safe_load(text)
    except PolicyYamlError:
        raise
    except yaml.YAMLError as exc:
        raise PolicyYamlError("yaml_parse_error") from exc
    if not is_bounded_json(parsed):
        raise PolicyYamlError("policy_bounded_json")
    return parsed


def read_bounded_policy(path: Path) -> object:
    """Read at most one byte beyond the authoring YAML budget."""
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_YAML_BYTES + 1)
    except OSError as exc:
        raise PolicyYamlError("policy_read_error") from exc
    return load_bounded_policy(data)


__all__ = ["MAX_YAML_BYTES", "PolicyYamlError", "load_bounded_policy", "read_bounded_policy"]
