"""MCP prompts for blockchain module."""

from __future__ import annotations

from typing import Any


def register(mcp: Any) -> None:
    """Register blockchain prompts."""

    @mcp.prompt()
    def blockchain_create_economy(
        agent_count: str = "5",
        initial_balance: str = "1000",
    ) -> str:
        """Guide for bootstrapping an agent economy."""
        return f"""Help me bootstrap an agent economy.

Agents: {agent_count}
Initial Balance: {initial_balance} tokens each

Steps:
1. Check chain health (blockchain_health_check)
2. Seed wallets (blockchain_authoring_seed_economy)
3. Verify balances (blockchain_get_balance for each)
4. Check chain info (blockchain_get_chain_info)

Use blockchain authoring tools (requires BLOCKCHAIN_ENABLE_AUTHORING_TOOLS=1)."""

    @mcp.prompt()
    def blockchain_transfer_tokens(
        from_wallet: str = "wallet-agent-000",
        to_wallet: str = "wallet-agent-001",
        amount: str = "100",
    ) -> str:
        """Guide for transferring tokens between wallets."""
        return f"""Help me transfer tokens between wallets.

From: {from_wallet}
To: {to_wallet}
Amount: {amount}

Steps:
1. Check sender balance (blockchain_get_balance)
2. Check receiver exists (blockchain_get_wallet)
3. Execute transfer (blockchain_transfer)
4. Verify chain integrity (blockchain_verify_chain)"""

    @mcp.prompt()
    def blockchain_post_and_claim_bounty(
        poster: str = "wallet-agent-000",
        amount: str = "500",
    ) -> str:
        """Guide for posting and claiming a bounty."""
        return f"""Help me create and manage a bounty.

Poster Wallet: {poster}
Bounty Amount: {amount}

Steps:
1. Check poster balance (blockchain_get_balance)
2. Post bounty (blockchain_post_bounty)
3. List open bounties (blockchain_list_bounties)
4. Claim bounty (blockchain_claim_bounty)
5. Verify escrow release (blockchain_list_transactions)"""

    @mcp.prompt()
    def blockchain_audit_chain() -> str:
        """Guide for auditing the blockchain."""
        return """Help me audit the blockchain ledger.

Steps:
1. Get chain info (blockchain_get_chain_info)
2. Verify hash integrity (blockchain_verify_chain)
3. List recent transactions (blockchain_list_transactions)
4. Reconcile a wallet (blockchain_reconcile)
5. Summarize findings"""

    @mcp.prompt()
    def blockchain_troubleshoot() -> str:
        """Guide for troubleshooting blockchain issues."""
        return """Help me troubleshoot blockchain issues.

Steps:
1. Run health check (blockchain_health_check)
2. Get chain info (blockchain_get_chain_info)
3. Verify chain integrity (blockchain_verify_chain)
4. Check recent transactions for failures
5. Reconcile any suspect wallets"""
