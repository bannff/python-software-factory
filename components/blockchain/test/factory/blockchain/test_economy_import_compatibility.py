"""Public import, interface, and core compatibility for the economy facade."""
from __future__ import annotations

import asyncio

from factory.blockchain import interface
from factory.blockchain.runtime.ports import LedgerPort
from factory.blockchain.runtime.runtime import BlockchainRuntime


def test_public_interface_exports_create_server_and_runtime_module() -> None:
    runtime = interface.runtime.BlockchainRuntime("mock")
    server = interface.create_server(runtime)
    tools = {tool.name for tool in asyncio.run(server.list_tools())}
    assert "blockchain_get_chain_info" in tools
    assert runtime.get_ledger().health_check()["provider"] == "mock_ledger"


def test_legacy_ledger_port_and_core_convenience_operations_remain_usable() -> None:
    runtime = BlockchainRuntime()
    ledger = runtime.get_ledger()
    typed_ledger: LedgerPort = ledger
    assert typed_ledger is runtime.get_ledger()
    assert ledger.health_check()["provider"] == "mock_ledger"

    interface.core.reset_runtime()
    try:
        wallet = interface.core.create_wallet("interface-compat", initial_balance=4)
        transfer = interface.core.transfer(wallet["wallet_id"], "wallet-treasury", 1)
        assert interface.core.get_balance(wallet["wallet_id"]) == 3
        assert transfer["tx_type"] == "transfer"
    finally:
        interface.core.reset_runtime()
