"""Map authoring-input failures to typed, public tool failure codes (#342)."""
from __future__ import annotations

import yaml
from factory.mcp_utils.interface import TypedToolFailure
from pydantic import ValidationError

from ..authoring import AuthoringError


def definition_failure(exc: Exception) -> TypedToolFailure | None:
    """Return the typed failure for a caller-fixable definition error, else None.

    Callers get ``workflow_definition_invalid:<field>`` so a form can point at the
    offending field; anything unexpected stays the opaque sentinel.
    """
    if isinstance(exc, ValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", ())) or "definition"
        return TypedToolFailure(f"workflow_definition_invalid:{field}", str(exc))
    if isinstance(exc, yaml.YAMLError):
        return TypedToolFailure("workflow_yaml_invalid", str(exc))
    if isinstance(exc, AuthoringError):
        code = "workflow_id_invalid" if str(exc).startswith("Invalid id") else "workflow_definition_invalid"
        return TypedToolFailure(code, str(exc))
    return None
