"""Record a neutral Finding by hand (no agent or chat model required)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

from factory.mcp_utils.interface import ToolResult, TypedToolFailure, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.ports import Entity
from .finding_contracts import FindingSubject, FindingTaxonomyRef, RecordFindingInput, RecordFindingOutput

if TYPE_CHECKING:
    from ..runtime.runtime import GraphRuntime


# First value of the existing verification-oracle states (graph FINDING_STATES).
INITIAL_STATE = "candidate"


def _properties(args: dict[str, Any], subject: FindingSubject | None,
                taxonomy: list[FindingTaxonomyRef]) -> dict[str, Any]:
    props = {k: v for k, v in args.items() if v not in ("", None)}
    props["state"] = INITIAL_STATE
    props["created_at"] = datetime.now(timezone.utc).isoformat()
    if subject is not None:
        props.update(subject_type=subject.type, subject_id=subject.id, location=subject.location)
    # CWE is the one scheme the legacy column and the neutral taxonomy share.
    cwe = next((t.id for t in taxonomy if t.scheme.lower() == "cwe"), "")
    if cwe:
        props["cwe"] = cwe
    return props


def register(mcp: Any, get_runtime: Callable[[], "GraphRuntime"]) -> None:
    @typed_tool(mcp)
    @operational(input_model=RecordFindingInput, output_model=RecordFindingOutput)
    def graph_record_finding(
        title: str, severity: str, kind: str = "other", category: str = "",
        description: str = "", evidence: str = "", remediation: str = "",
        subject: FindingSubject | None = None, taxonomy: list[FindingTaxonomyRef] | None = None,
        run_id: str = "", app: str = "", backend: str = "",
    ) -> ToolResult[RecordFindingOutput]:
        subject = None if subject is None else FindingSubject.model_validate(subject)
        taxonomy = [FindingTaxonomyRef.model_validate(t) for t in taxonomy or []]
        runtime = get_runtime()
        selected = backend or runtime.default_backend
        available = runtime.available_backends()
        if selected not in available:
            raise TypedToolFailure("unknown_backend", ", ".join(available))
        finding_id = f"finding-{uuid4().hex}"
        props = _properties(
            dict(title=title, severity=severity, kind=kind, category=category,
                 description=description, evidence=evidence, remediation=remediation,
                 run_id=run_id, app=app),
            subject, taxonomy)
        runtime.get_graph(selected).add_entity(Entity(finding_id, "Finding", props, ["Finding"]))
        return RecordFindingOutput(finding_id=finding_id, state=INITIAL_STATE)
