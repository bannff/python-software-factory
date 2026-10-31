"""API lifespan closes the process-owned chat runtime."""
from __future__ import annotations

import pytest
from fastapi import FastAPI


@pytest.mark.asyncio
async def test_api_lifespan_closes_chat_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    from factory.agent import interface as agent_interface
    from factory.api.runtime.adapters.rest import RESTAdapter

    closed: list[bool] = []

    async def close_chat_agent() -> None:
        closed.append(True)

    monkeypatch.setattr(
        agent_interface, "close_chat_agent", close_chat_agent, raising=False,
    )
    from factory.api.runtime.background_tasks import install_runtime_lifespan

    adapter = RESTAdapter.__new__(RESTAdapter)
    adapter._app = FastAPI()
    install_runtime_lifespan(adapter._app)
    async with adapter._app.router.lifespan_context(adapter._app):
        pass
    assert closed == [True]
