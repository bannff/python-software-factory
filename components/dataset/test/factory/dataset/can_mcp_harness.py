"""Production-shaped progressive MCP harness for Dataset CAN acceptance."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.mcp_server.interface import MCPAggregator
from factory.mcp_utils.interface import get_service, set_service

MINIMAL_DBC = '''VERSION "1.0"
NS_ :
BS_:
BU_: ECU
BO_ 257 MOTION: 8 ECU
 SG_ VehicleSpeed : 0|16@1+ (0.1,0) [0|250] "km/h" ECU
'''


class ProgressiveCanHarness:
    """Drive named tools through the same aggregator methods as production."""

    def __init__(self, storage_root: Path) -> None:
        self._env = patch.dict(os.environ, {
            "DATASET_STORAGE_ROOT": str(storage_root),
            "GRAPH_BACKEND": "networkx",
        })
        self._previous = None
        self.aggregator: MCPAggregator | None = None

    def __enter__(self) -> "ProgressiveCanHarness":
        self._env.start()
        try:
            aggregator = MCPAggregator(ToolCatalog("can-acceptance"))
            aggregator.set_available_bricks(["dataset", "graph"])
            for brick in ("dataset", "graph"):
                discovered = aggregator.get_brick_tools(brick)
                if "error" in discovered:
                    raise RuntimeError(discovered["error"])
            self.aggregator = aggregator
            self._previous = get_service("tool_invoker")
            set_service("tool_invoker", aggregator.invoke_tool)
            return self
        except Exception:
            self._env.stop()
            raise

    def __exit__(self, *_exc) -> None:
        set_service("tool_invoker", self._previous)
        self._env.stop()

    def dispatch(
        self, brick: str, tool_name: str, arguments: dict | None = None,
    ) -> dict:
        assert self.aggregator is not None
        return asyncio.run(self.aggregator.call_brick_tool(
            brick, tool_name, arguments or {},
        ))

    def call(self, brick: str, tool_name: str, arguments: dict | None = None):
        envelope = self.dispatch(brick, tool_name, arguments)
        if not envelope.get("ok"):
            raise RuntimeError(envelope["error"]["message"])
        result = envelope["result"]
        structured = result.get("structured_content")
        meta = result.get("meta") or {}
        if brick == "dataset" and isinstance(structured, dict) and structured.get("schema_version") == "v1":
            if structured.get("ok") is not True:
                raise RuntimeError(str(structured.get("error")))
            return structured.get("data")
        return structured


def rows(uri: str) -> list[dict]:
    path = Path(uri.removeprefix("file://"))
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def materialize(
    mcp: ProgressiveCanHarness, root: Path, attempt: str,
    refs: list[dict], dbc_path: str = "",
) -> dict:
    arguments = {
        "attempt_id": attempt, "mf4_dir": str(root),
        "vehicle_id": "fixture-car", "vehicle_alias": "fixture-car",
        "vehicle_make": "Fixture", "vehicle_model": "Car", "vehicle_year": 2026,
        "failure_pattern_refs": refs, "storage_root": str(root),
        "max_samples": 100,
        "config_overrides": {"synthesize": {"multiplier": 1}},
    }
    if dbc_path:
        arguments["dbc_path"] = dbc_path
    return mcp.call("dataset", "dataset_materialize_can_training_bundle", arguments)


__all__ = ["MINIMAL_DBC", "ProgressiveCanHarness", "materialize", "rows"]
