"""Seed or archive deterministic M1 Session Deck visual fixtures.

Uses the standard same-origin Next BFF for Session metadata, inheriting the exact
local UI identity without reading its bearer, and the official LangGraph SQLite
saver for deterministic transcript checkpoints. No bearer, user content, or model
call leaves localhost.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

_FIXTURE = Path("/tmp/python-factory-m1-evidence/session-fixture.json")
_SESSIONS = (
    ("Persistent session proof", "Remember the launch checklist.",
     "The launch checklist is saved in this durable session."),
    ("Steering delivery review", "Did the steering message arrive?",
     "Yes. Delivery remained truthful and correlated to the original message."),
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup", action="store_true")
    return parser.parse_args()


def _data(result: Any) -> dict[str, Any]:
    outer = result.structured_content
    transport = outer.get("data", {}) if isinstance(outer, dict) else {}
    structured = transport.get("result", {}).get("structured_content", {})
    if structured.get("ok") is not True or not isinstance(structured.get("data"), dict):
        raise RuntimeError("fixture MCP operation failed")
    return structured["data"]


async def _call(session: ClientSession, brick: str, tool: str, arguments: dict[str, Any]):
    result = await session.call_tool("call_brick_tool", {
        "brick_name": brick, "tool_name": tool,
        "arguments": json.dumps(arguments, separators=(",", ":")),
    })
    return _data(result)


async def _archive_existing(session: ClientSession) -> None:
    active = (await _call(session, "session", "list", {
        "include_archived": False,
    }))["sessions"]
    for item in active:
        if item.get("origin") != "visual-acceptance":
            continue
        try:
            await _call(session, "session", "archive", {
                "session_id": item["session_id"],
                "expected_revision": item["revision"],
            })
        except RuntimeError:
            pass
    _FIXTURE.unlink(missing_ok=True)


async def _write_history(agent_id: str, thread_id: str, user: str, assistant: str) -> None:
    path = os.getenv("COMPANION_X_CHECKPOINT_DB_PATH", "./.storage/agent-checkpoints.db")
    connection = await aiosqlite.connect(path)
    try:
        await connection.execute("PRAGMA journal_mode=WAL")
        saver = AsyncSqliteSaver(connection)
        await saver.setup()
        checkpoint = empty_checkpoint()
        checkpoint["channel_values"] = {"messages": [
            HumanMessage(content=user, id=f"fixture-user-{uuid4().hex}"),
            AIMessage(content=assistant, id=f"fixture-assistant-{uuid4().hex}"),
        ]}
        await saver.aput(
            {"configurable": {
                "thread_id": f"{agent_id}-{thread_id}", "checkpoint_ns": "",
            }},
            checkpoint, {"source": "input", "step": 0, "parents": {}}, {},
        )
    finally:
        await connection.close()


async def _run(cleanup: bool) -> None:
    headers = {
        "Origin": "http://127.0.0.1:3000",
        "x-companion-x-local": "1",
    }
    http = create_mcp_http_client(headers=headers)
    async with http:
        async with streamable_http_client(
            "http://127.0.0.1:3000/mcp", http_client=http,
        ) as streams:
            async with ClientSession(*streams[:2]) as session:
                await session.initialize()
                await _archive_existing(session)
                if cleanup:
                    print("m1-session-fixture: CLEAN")
                    return
                seeded = []
                for title, user, assistant in _SESSIONS:
                    record = (await _call(session, "session", "create", {
                        "title": title, "agent_id": "companion-x-default",
                        "model": "fixture", "origin": "visual-acceptance",
                    }))["session"]
                    await _write_history(record["agent_id"], record["thread_id"], user, assistant)
                    history = await _call(session, "agent", "session_history", {
                        "session_id": record["session_id"],
                    })
                    if len(history["messages"]) != 2:
                        raise RuntimeError("fixture history verification failed")
                    seeded.append(record)
                _FIXTURE.parent.mkdir(parents=True, exist_ok=True)
                _FIXTURE.write_text(json.dumps({"sessions": seeded}, indent=2) + "\n")
                print("m1-session-fixture: READY (2 sessions, 4 messages)")


def main() -> int:
    asyncio.run(_run(_arguments().cleanup))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
