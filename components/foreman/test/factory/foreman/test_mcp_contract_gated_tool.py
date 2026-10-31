"""The typed-boundary ratchet must keep auditing ``@gated_tool`` registrations.

``gated_tool`` is the per-action registration gate: when the surface/action is
denied it hands the function back unregistered, and when allowed it calls
``mcp.tool()`` itself. Either way the decorator is the registration site, so
the contract inventory has to see it — otherwise the typed-boundary ratchet
would silently stop auditing exactly the gated tools.
"""
from __future__ import annotations

from pathlib import Path

from factory.foreman.mcp_contract_check import inventory_mcp_contracts

_GATED_UNTYPED = '''from pydantic import BaseModel, ConfigDict
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
@gated_tool(mcp, policy, "skills", "add")
@authoring(input_model=Strict, output_model=Strict)
def gated() -> dict: return {}
'''


def test_inventory_audits_a_gated_registration(tmp_path: Path) -> None:
    path = tmp_path / "components/demo/src/factory/demo/mcp/tools.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_GATED_UNTYPED)

    issues = {item["issue"] for item in inventory_mcp_contracts(tmp_path)}
    assert issues == {"output_not_tool_result", "raw_container_egress"}


def test_inventory_accepts_a_typed_gated_registration(tmp_path: Path) -> None:
    path = tmp_path / "components/demo/src/factory/demo/mcp/tools.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('''from pydantic import BaseModel, ConfigDict
from factory.mcp_utils.interface import ToolResult
class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
class OutputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
@gated_tool(mcp, policy, "skills", "add")
@authoring(input_model=InputDTO, output_model=OutputDTO)
def gated() -> ToolResult[OutputDTO]: return None
''')

    assert not inventory_mcp_contracts(tmp_path)


def test_the_real_gated_tools_are_audited() -> None:
    """Strip the typed boundary from the real gated tools: they must be caught."""
    rel = "components/agent/src/factory/agent/mcp/skills_tools.py"
    root = Path(__file__).parents[5]
    sources = {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for path in root.glob("components/*/src/factory/**/*.py")
    }
    assert rel in sources
    mutated = "\n".join(
        line for line in sources[rel].splitlines() if not line.strip().startswith("@authoring(")
    )
    assert mutated != sources[rel]

    audited = {
        item["tool"]
        for item in inventory_mcp_contracts(root, sources={**sources, rel: mutated})
    }
    assert {"agent_add_skill", "agent_delete_skill"} <= audited
    assert "agent_list_skills" not in audited
