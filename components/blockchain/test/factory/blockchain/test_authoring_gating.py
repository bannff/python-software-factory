"""Tests for blockchain authoring gating."""

import os
from unittest.mock import patch

from factory.blockchain.runtime.runtime import BlockchainRuntime


def test_runtime_creates_ledger():
    runtime = BlockchainRuntime()
    ledger = runtime.get_ledger()
    assert ledger is not None
    health = ledger.health_check()
    assert health["healthy"] is True


def test_authoring_env_var_gating():
    with patch.dict(os.environ, {}, clear=True):
        assert os.environ.get("BLOCKCHAIN_ENABLE_AUTHORING_TOOLS") != "1"

    with patch.dict(os.environ, {"BLOCKCHAIN_ENABLE_AUTHORING_TOOLS": "1"}):
        assert os.environ.get("BLOCKCHAIN_ENABLE_AUTHORING_TOOLS") == "1"
