from __future__ import annotations

import asyncio

from factory.sandbox.interface import Runtime
from factory.sandbox.runtime.adapters.mock import MockAdapter
from factory.sandbox.server import create_tool_catalog


def _tools():
    catalog = create_tool_catalog(Runtime(MockAdapter()))
    return {t.name: t.fn for t in asyncio.run(catalog.list_tools())}


def test_terminate_of_an_unknown_env_is_typed() -> None:
    tools = _tools()
    assert asyncio.run(tools["sandbox.terminate"](env_id="env-nope")).error == "env_not_found"


def test_unknown_profile_and_preset_have_their_own_codes() -> None:
    tools = _tools()
    assert asyncio.run(tools["sandbox.provision"](profile="no-such-profile")).error == "unknown_profile"
    bad_preset = asyncio.run(tools["sandbox.provision"](profile="web-server", device_preset="no-such-preset"))
    assert bad_preset.error in {"unknown_device_preset", "unknown_profile"}


def test_a_provisioned_env_terminates_and_lists_its_current_status() -> None:
    tools = _tools()
    env_id = asyncio.run(tools["sandbox.provision"]()).data.environment.env_id
    listed = asyncio.run(tools["sandbox.list_environments"]()).data.environments
    assert next(e for e in listed if e.env_id == env_id).status != "provisioning"
    assert asyncio.run(tools["sandbox.terminate"](env_id=env_id)).ok
