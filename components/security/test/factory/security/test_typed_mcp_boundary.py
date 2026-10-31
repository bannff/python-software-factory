"""Fresh-server proofs for Security's typed FastMCP boundary."""
from __future__ import annotations

import asyncio
from typing import get_type_hints

import pytest

from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.security.interface import create_server
from factory.security.mcp.contracts.base import DTO


EXPECTED = {
    "deterministic": {
        "security.get_capabilities", "security.health_check",
        "security.describe_config_schema", "security.list_analyses",
        "security.get_analysis", "security.supported_types",
        "security.scan_endpoints", "security.classify_confidence",
        "security.trace_taint", "security_pentest_list_jobs", "security_get_views",
    },
    "operational": {
        "security.analyze", "security.threat_model", "security.code_review",
        "security.recon", "security.list_persisted_findings",
        "security.list_persisted_analyses", "security_classify_finding",
        "security_conform_finding", "security_ingest_gt_entry",
        "security_list_findings_for_run", "security_pentest_scan",
        "security_pentest_status", "security_pentest_results", "security_pentest_cancel",
    },
    "authoring": {
        "security.authoring.get_status", "security.authoring.list_rules",
        "security.authoring.upsert_rule", "security.authoring.delete_rule",
        "security_seed_cwe_taxonomy", "security_seed_ocsf_taxonomy",
    },
}


def _tools():
    server = create_server()
    names = [tool.name for tool in asyncio.run(server.list_tools())]
    return server, {name: asyncio.run(server.get_tool(name)) for name in names}


def test_fresh_server_has_exact_typed_security_surface() -> None:
    _, tools = _tools()
    actual = {category: set() for category in EXPECTED}
    for name, tool in tools.items():
        fn = tool.fn
        category = fn._mcp_category
        actual[category].add(name)
        input_model, output_model = fn._mcp_input_model, fn._mcp_output_model
        assert issubclass(input_model, DTO)
        assert issubclass(output_model, DTO)
        assert input_model.model_config["extra"] == "forbid"
        assert input_model.model_config["strict"] is True
        assert get_type_hints(fn)["return"] == ToolResult[output_model]
    assert actual == EXPECTED


def test_fastmcp_flat_ingress_and_envelope_are_strict() -> None:
    server, tools = _tools()
    del server
    analyze = tools["security.analyze"].fn
    result = asyncio.run(analyze(target="target"))
    assert result.ok is True and result.data.success is True
    with pytest.raises(SchemaMigrationError):
        asyncio.run(analyze(target="target", unknown=True))
    with pytest.raises(SchemaMigrationError):
        asyncio.run(analyze(target=1))


def test_views_tool_returns_the_typed_envelope() -> None:
    _, tools = _tools()
    result = tools["security_get_views"].fn()
    assert result.ok is True
    assert result.data.views[0]["id"] == "security-dashboard"


class _ThreatModelLLM:
    async def complete_async(self, *args, **kwargs):
        class _Response:
            content = "STRIDE analysis"
        return _Response()


def test_threat_model_envelopes_both_runtime_shapes() -> None:
    from factory.security.runtime.adapters.mock import MockAnalyzerAdapter
    from factory.security.runtime.runtime import SecurityRuntime

    unavailable = create_server(runtime=SecurityRuntime(MockAnalyzerAdapter()))
    unavailable_tool = asyncio.run(unavailable.get_tool("security.threat_model")).fn
    unavailable_result = asyncio.run(unavailable_tool(target="payments"))
    assert unavailable_result.ok is True
    assert unavailable_result.data.model_dump(exclude_none=True) == {
        "error": "LLM adapter not configured — compose llm_gateway brick",
    }

    available = create_server(
        runtime=SecurityRuntime(MockAnalyzerAdapter(), llm=_ThreatModelLLM()),
    )
    available_tool = asyncio.run(available.get_tool("security.threat_model")).fn
    available_result = asyncio.run(available_tool(target="payments"))
    assert available_result.ok is True
    assert available_result.data.model_dump(exclude_none=True) == {
        "target": "payments", "analysis": "STRIDE analysis",
    }


class _Pentest:
    async def scan(self, scan_type, target, options):
        from factory.security.runtime.ports import ScanJob
        return ScanJob(
            job_id="scan-1", scan_type=scan_type, target=target,
            status="completed", started_at="now", env_id="sandbox-1",
        )

    async def get_status(self, job_id):
        return {"job_id": job_id, "status": "completed"}

    async def get_results(self, job_id):
        from factory.security.runtime.ports import ScanResults, ScanType
        return ScanResults(
            job_id=job_id, scan_type=ScanType.http_probe, raw_output="200 OK",
            findings=[{"severity": "low"}], duration_ms=7, exit_code=0,
        )


def test_pentest_preserves_legacy_payload_fields_at_data_top_level() -> None:
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
    from factory.security.mcp import pentest_tools

    mcp = ToolCatalog("pentest-regression")
    pentest_tools.register(mcp, _Pentest())
    scan = asyncio.run(mcp.get_tool("security_pentest_scan")).fn
    status = asyncio.run(mcp.get_tool("security_pentest_status")).fn
    results = asyncio.run(mcp.get_tool("security_pentest_results")).fn

    invalid = asyncio.run(scan(scan_type="unknown", target="example.test"))
    assert invalid.ok is True
    assert invalid.data.model_dump(exclude_none=True) == {
        "error": "Invalid scan_type: unknown",
        "valid": ["port_scan", "vuln_scan", "web_fuzz", "sql_inject", "http_probe", "nuclei_scan"],
    }
    launched = asyncio.run(scan(scan_type="http_probe", target="example.test"))
    assert launched.ok is True
    assert launched.data.model_dump(exclude_none=True) == {
        "job_id": "scan-1", "scan_type": "http_probe", "target": "example.test",
        "status": "completed", "started_at": "now", "env_id": "sandbox-1",
    }
    assert "job" not in launched.data.model_dump()

    state = asyncio.run(status(job_id="scan-1"))
    assert state.ok is True
    assert state.data.model_dump(exclude_none=True) == {
        "job_id": "scan-1", "status": "completed",
    }
    report = asyncio.run(results(job_id="scan-1"))
    assert report.ok is True
    assert report.data.model_dump() == {
        "job_id": "scan-1", "scan_type": "http_probe", "raw_output": "200 OK",
        "findings": [{"severity": "low"}], "duration_ms": 7, "exit_code": 0,
    }
