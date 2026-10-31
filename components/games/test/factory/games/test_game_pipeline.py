"""Tests for game pipeline MCP orchestration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.blockchain.mcp.contracts.ledger import TransactionOutput
from factory.blockchain.mcp.contracts.operational import CreateWalletOutput
from factory.blockchain.mcp.contracts.deterministic import GetWalletOutput
from factory.games.runtime.game_pipeline import process_game_finished
from factory.mcp_utils.interface import ToolResult


def _make_payload(**overrides) -> dict:
    base = {"game_id": "test-001", "game_type": "ctf_challenge", "winner": 1, "reward": {1: 1.0}, "move_count": 5, "move_history": [{"action": "execute", "command": "ls"}, {"action": "read_file", "path": "/etc/passwd"}, {"action": "execute", "command": "cat flag.txt"}, {"action": "submit_flag", "flag": "wrong"}, {"action": "submit_flag", "flag": "CTF{correct}"}], "config": {"challenge_id": "ch-1", "difficulty": "easy"}, "players": {1: "agent-alpha"}}
    base.update(overrides)
    return base


class TestGamePipelineNoInvoker:
    @patch("factory.games.runtime.game_pipeline._get_invoker", return_value=None)
    def test_all_skipped_without_invoker(self, _mock):
        result = process_game_finished(_make_payload())
        assert result["graph"]["skipped"] is True
        assert result["blockchain"]["skipped"] is True
        assert result["evals"]["skipped"] is True

    @patch("factory.games.runtime.game_pipeline._get_invoker", return_value=None)
    def test_no_winner_skips_blockchain(self, _mock):
        assert process_game_finished(_make_payload(winner=None))["blockchain"]["skipped"] is True


class TestGamePipelineWithInvoker:
    def _mock_invoker(self):
        invoker = MagicMock()
        invoker.return_value = {"ok": True}
        return invoker

    @patch("factory.games.runtime.game_pipeline._get_invoker")
    def test_graph_stores_transcript(self, mock_get):
        invoker = self._mock_invoker()
        mock_get.return_value = invoker
        result = process_game_finished(_make_payload())
        assert len([call for call in invoker.call_args_list if call[0][0] == "graph_graph_add_entity"]) == 6
        assert result["graph"] == {"stored": True, "moves": 5}

    @patch("factory.games.runtime.game_pipeline._get_invoker")
    def test_blockchain_mints_reward(self, mock_get):
        invoker = self._mock_invoker()
        missing = GetWalletOutput(wallet_id="wallet-agent-alpha", owner_id="", balance=0, created_at="", found=False, error="not_found")
        created = CreateWalletOutput(wallet_id="wallet-agent-alpha", owner_id="agent-alpha", balance=0, created_at="")
        minted = TransactionOutput(tx_id="tx-1", tx_type="mint", to_wallet="wallet-agent-alpha", amount=100, memo="", status="committed")
        invoker.side_effect = lambda tool, **_kw: ToolResult(data=missing) if tool == "blockchain_get_wallet" else ToolResult(data=created) if tool == "blockchain_create_wallet" else ToolResult(data=minted) if tool == "blockchain_mint" else {"ok": True}
        mock_get.return_value = invoker
        result = process_game_finished(_make_payload())
        assert result["blockchain"]["claimed"] is True
        assert result["blockchain"]["amount"] == 100.0

    @patch("factory.games.runtime.game_pipeline._get_invoker")
    def test_no_winner_skips_bounty(self, mock_get):
        mock_get.return_value = self._mock_invoker()
        result = process_game_finished(_make_payload(winner=None))
        assert result["blockchain"] == {"skipped": True, "reason": "no winner"}

    @patch("factory.games.runtime.game_pipeline._get_invoker")
    def test_evals_scores_ctf(self, mock_get):
        invoker = self._mock_invoker()
        mock_get.return_value = invoker
        assert process_game_finished(_make_payload())["evals"]["scored"] is True
        assert len([call for call in invoker.call_args_list if call[0][0] == "evals_evaluate"]) == 1

    @patch("factory.games.runtime.game_pipeline._get_invoker")
    def test_unknown_game_type_skips_evals(self, mock_get):
        mock_get.return_value = self._mock_invoker()
        result = process_game_finished(_make_payload(game_type="unknown_game"))
        assert result["evals"] == {"skipped": True, "reason": "no rubric for game type"}


    @patch("factory.games.runtime.game_pipeline._get_invoker")
    def test_blockchain_failed_typed_mint_is_not_claimed(self, mock_get):
        invoker = self._mock_invoker()
        existing = GetWalletOutput(
            wallet_id="wallet-agent-alpha", owner_id="agent-alpha", balance=0,
            created_at="",
        )
        rejected = TransactionOutput(success=False, error="treasury unavailable")
        invoker.side_effect = lambda tool, **_kw: (
            ToolResult(data=existing) if tool == "blockchain_get_wallet"
            else ToolResult(data=rejected) if tool == "blockchain_mint"
            else {"ok": True}
        )
        mock_get.return_value = invoker

        result = process_game_finished(_make_payload())

        assert result["blockchain"] == {"skipped": True, "error": "treasury unavailable"}
