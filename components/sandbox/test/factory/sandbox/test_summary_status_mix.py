"""A provisioned env must show up in the dashboard status mix (#381)."""
from __future__ import annotations

import asyncio

from factory.sandbox.interface import Runtime
from factory.sandbox.mcp.dashboard_summary import build_dashboard_summary
from factory.sandbox.runtime.adapters.mock import MockAdapter


def test_status_mix_counts_a_provisioned_environment() -> None:
    runtime = Runtime(MockAdapter())
    asyncio.run(runtime.provision())
    summary = build_dashboard_summary(runtime)
    assert sum(item["value"] for item in summary["series"]) == 1
