"""Focused AST inventory and Git-base ratchet tests for public MCP tools."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import factory.foreman.mcp_contract_check as contracts

_GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "Guardian Test", "GIT_AUTHOR_EMAIL": "guardian@example.test", "GIT_COMMITTER_NAME": "Guardian Test", "GIT_COMMITTER_EMAIL": "guardian@example.test"}


def _write(root: Path, name: str, source: str) -> None:
    path = root / f"components/demo/src/factory/demo/mcp/{name}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)


def _tool(models: str, decorator: str, returns: str = "Strict") -> str:
    return f'''from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict
mcp = FastMCP("demo")
{models}
@mcp.tool()
@deterministic({decorator})
def typed() -> {returns}: return None
'''


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, env=_GIT_ENV, capture_output=True, text=True, check=True).stdout.strip()


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def test_inventory_reports_unresolved_non_pydantic_and_raw_egress(tmp_path: Path) -> None:
    _write(tmp_path, "tools", _tool('''class Strict(BaseModel): model_config = ConfigDict(extra="forbid")
class Impostor: model_config = ConfigDict(extra="forbid")''', "input_model=Impostor, output_model=Missing", "dict") + '''
@mcp.tool()
@deterministic(input_model=Strict, output_model=Impostor)
def non_pydantic_output() -> Strict: return None
''')
    issues = {item["issue"] for item in contracts.inventory_mcp_contracts(tmp_path)}
    assert issues == {"non_pydantic_input_model", "unresolved_output_model", "non_pydantic_output_model", "raw_container_egress"}


def test_inventory_accepts_same_brick_pydantic_models_and_always_reports_raw_egress(tmp_path: Path) -> None:
    _write(tmp_path, "models", 'from pydantic import BaseModel, ConfigDict\nclass Strict(BaseModel): model_config = ConfigDict(extra="forbid")')
    _write(tmp_path, "tools", '''from fastmcp import FastMCP
import factory.demo.mcp.models as models
mcp = FastMCP("demo")
@mcp.tool()
@deterministic(input_model=models.Strict, output_model=models.Strict)
def typed() -> dict: return {}
''')
    violations = contracts.inventory_mcp_contracts(tmp_path)
    assert {item["issue"] for item in violations} == {"output_not_tool_result", "raw_container_egress"}


def test_inventory_accepts_category_neutral_typed_boundary(tmp_path: Path) -> None:
    _write(tmp_path, "tools", '''from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict
from factory.mcp_utils.interface import ToolResult, typed
mcp = FastMCP("demo")
class InputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
class OutputDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
@mcp.tool()
@typed(input_model=InputDTO, output_model=OutputDTO)
def typed() -> ToolResult[OutputDTO]: return None
''')
    assert not contracts.inventory_mcp_contracts(tmp_path)


def test_inventory_accepts_strict_root_model_outputs(tmp_path: Path) -> None:
    _write(tmp_path, "models", '''from pydantic import RootModel
class Strict(RootModel[dict[str, str]]): pass''')
    _write(tmp_path, "tools", '''from fastmcp import FastMCP
from factory.mcp_utils.interface import ToolResult
from factory.demo.mcp.models import Strict
mcp = FastMCP("demo")
@mcp.tool()
@deterministic(input_model=Strict, output_model=Strict)
def typed() -> ToolResult[Strict]: return None
''')
    assert not contracts.inventory_mcp_contracts(tmp_path)


def test_inventory_requires_forbidden_extras_on_ingress_and_egress(tmp_path: Path) -> None:
    _write(tmp_path, "tools", _tool(
        '''class Strict(BaseModel): model_config = ConfigDict(extra="forbid")
class Relaxed(BaseModel): pass''',
        "input_model=Strict, output_model=Relaxed", "ToolResult[Relaxed]",
    ).replace(
        "from pydantic import BaseModel, ConfigDict",
        "from pydantic import BaseModel, ConfigDict\nfrom factory.mcp_utils.interface import ToolResult",
    ))
    violations = contracts.inventory_mcp_contracts(tmp_path)
    assert [item["issue"] for item in violations] == ["output_model_extra_not_forbid"]


def test_identity_ratchet_blocks_new_tool_and_allows_legacy_deletion(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-b", "main")
    legacy = _tool("", "", "dict")
    _write(tmp_path, "tools", legacy)
    base = _commit(tmp_path, "legacy debt")
    assert contracts.check_mcp_contracts(tmp_path, base)["passed"] is True
    _write(tmp_path, "tools", legacy + _tool("", "", "dict").replace("def typed", "def introduced"))
    _commit(tmp_path, "new debt")
    result = contracts.check_mcp_contracts(tmp_path, base)
    assert result["passed"] is False
    assert {item["tool"] for item in result["new_violations"]} == {"introduced"}
    _write(tmp_path, "tools", "")
    _commit(tmp_path, "delete debt")
    result = contracts.check_mcp_contracts(tmp_path, base)
    assert result["passed"] is True
    assert result["resolved_violations"]


def test_absent_base_is_informative_and_non_blocking(tmp_path: Path) -> None:
    _write(tmp_path, "tools", _tool("", "", "dict"))
    result = contracts.check_mcp_contracts(tmp_path)
    assert result["passed"] is True
    assert result["mode"] == "informational"
    assert result["legacy_violations"]


def test_evals_public_tools_have_no_contract_inventory_violations() -> None:
    root = Path(__file__).parents[5]
    violations = contracts.inventory_mcp_contracts(root)
    assert not [item for item in violations if item["brick"] == "evals"]


def test_native_transport_exemption_rejects_a_noncanonical_endpoint() -> None:
    source = '''from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, RootModel
from factory.mcp_utils.interface import operational
from .mcp_contracts import native_transport_egress
mcp = FastMCP("mcp-server")
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
class NativeTransportOutput(RootModel[dict[str, str]]): pass
@mcp.tool()
@native_transport_egress(output_model=NativeTransportOutput)
@operational(input_model=Strict)
def call_brick_tool() -> dict: return {}
'''
    issues = contracts.inventory_mcp_contracts(
        sources={
            "bases/mcp_server/src/factory/mcp_server/runtime/other.py": source,
        }
    )
    assert {item["issue"] for item in issues} == {
        "unresolved_output_model", "raw_container_egress",
    }


def test_inventory_recognizes_neutral_catalog_registration(tmp_path: Path) -> None:
    _write(tmp_path, "tools", '''from pydantic import BaseModel, ConfigDict
from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
catalog = ToolCatalog("demo")
class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
@catalog.tool()
@deterministic(input_model=Strict, output_model=Strict)
def typed() -> dict: return {}
''')
    assert {item["issue"] for item in contracts.inventory_mcp_contracts(tmp_path)} == {
        "output_not_tool_result", "raw_container_egress",
    }
