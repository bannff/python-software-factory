"""Process, MCP transport, and fixture support for real API acceptance."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from asammdf import MDF, Signal
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

REPO = Path(__file__).parents[2]


def available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def write_fixture(root: Path) -> tuple[Path, Path]:
    capture = root / "capture"
    capture.mkdir(parents=True)
    dbc = capture / "fixture.dbc"
    dbc.write_text(
        'VERSION "fixture"\nNS_ :\nBS_:\nBU_: ECU\n'
        'BO_ 256 FixtureMessage: 8 ECU\n'
        ' SG_ Speed : 0|8@1+ (1,0) [0|255] "" ECU\n'
    )
    dtype = np.dtype([
        ("CAN_DataFrame.BusChannel", "u1"),
        ("CAN_DataFrame.ID", "<u4"),
        ("CAN_DataFrame.IDE", "u1"),
        ("CAN_DataFrame.DLC", "u1"),
        ("CAN_DataFrame.DataBytes", "u1", (8,)),
        ("CAN_DataFrame.EDL", "u1"),
    ])
    samples = np.zeros(80, dtype=dtype)
    samples["CAN_DataFrame.BusChannel"] = 1
    samples["CAN_DataFrame.ID"] = 0x100
    samples["CAN_DataFrame.DLC"] = 8
    samples["CAN_DataFrame.DataBytes"][:, 0] = np.arange(80) % 64
    signal = Signal(
        samples, np.arange(80, dtype=np.float64) * 10,
        name="CAN_DataFrame", master_metadata=("Timestamp", 1),
    )
    mf4 = capture / "fixture.mf4"
    mdf = MDF(version="4.10")
    mdf.append(signal)
    mdf.save(mf4, overwrite=True)
    mdf.close()
    return capture, dbc


def _environment(root: Path, port: int) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("MCP_INCLUDE_BRICKS", None)
    env.update({
        "WORKSPACE_ROOT": str(REPO),
        "PROJECT_PYPROJECT": str(REPO / "projects/companion_x/pyproject.toml"),
        "WORKFLOW_CONFIG_DIR": str(REPO / "projects/companion_x/config"),
        "FACTORY_API_ADAPTER": "rest", "FACTORY_API_HOST": "127.0.0.1",
        "FACTORY_API_PORT": str(port), "FACTORY_API_RELOAD": "false",
        "MCP_DISCOVERY_MODE": "progressive",
        "ML_MODEL_PASSPORT_ROOT": str(root / "passports"),
        "ML_LIGHTGBM_MODEL_ROOT": str(root / "passports/models/lightgbm"),
        "ML_LNN_MODEL_ROOT": str(root / "passports/models/lnn"),
        "DATASET_STORAGE_ROOT": str(root / "passports" / "datasets"),
        "STORAGE_DOC_BACKEND": "sqlite",
        "ML_ENABLE_AUTHORING_TOOLS": "1",
    })
    return env


def start_api(root: Path, port: int, ordinal: int):
    log = (root / f"api-{ordinal}.log").open("w")
    process = subprocess.Popen(
        [sys.executable, "-m", "factory.api.main"], cwd=REPO,
        env=_environment(root, port), stdout=log, stderr=subprocess.STDOUT,
    )
    return process, log


async def wait_ready(process: subprocess.Popen, port: int, log_path: Path) -> None:
    async with httpx.AsyncClient(timeout=0.5) as client:
        for _ in range(240):
            if process.poll() is not None:
                raise AssertionError(log_path.read_text())
            try:
                response = await client.get(f"http://127.0.0.1:{port}/api/health")
                if response.status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.1)
    raise AssertionError(f"API did not start; log:\n{log_path.read_text()}")


def stop_api(process: subprocess.Popen, log) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    log.close()


@asynccontextmanager
async def mcp_session(port: int):
    async with streamable_http_client(f"http://127.0.0.1:{port}/mcp/") as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            yield session


def _value(result) -> Any:
    assert not result.isError, result.content
    value = result.structuredContent
    if value is None:
        text = next(item.text for item in result.content if hasattr(item, "text"))
        value = json.loads(text)
    while isinstance(value, dict):
        if set(value) == {"result"}:
            value = value["result"]
            continue
        if set(value) == {"ok", "result"}:
            assert value["ok"], value
            value = value["result"]
            continue
        if value.get("kind") == "tool" and "structured_content" in value:
            value = value["structured_content"]
            continue
        break
    return value


async def call(session: ClientSession, name: str, arguments: dict | None = None) -> Any:
    return _value(await session.call_tool(name, arguments or {}))


async def call_brick(
    session: ClientSession, brick: str, tool: str, arguments: dict,
) -> Any:
    return await call(session, "call_brick_tool", {
        "brick_name": brick, "tool_name": tool,
        "arguments": json.dumps(arguments, separators=(",", ":")),
    })


async def brick_call(session: ClientSession, tool: str, arguments: dict) -> Any:
    return await call_brick(session, "machine_learning", tool, arguments)


def raw_records() -> list[dict[str, Any]]:
    return [
        {"timestamp_ns": index * 10_000_000, "vehicle_id": "restart-fixture",
         "arbitration_id": "0x100", "decoded_signals": {"Speed": float(index + 1)},
         "is_failure": False}
        for index in range(13)
    ]
