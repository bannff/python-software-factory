"""Documentation for blockchain agent economy."""

ECONOMY_OVERVIEW = """# Agent Economy

Internal token economy for AI agents. Agents earn tokens by completing
bounties and spend tokens to request work. The ledger is hash-chained
and persists to the unified Neo4j graph.

## Why

Tokens give agents a quantifiable reward signal. This enables:
- Incentive-aligned task execution (agents optimize for token earnings)
- Auditable work history (every transaction is on-chain)
- RL training data (state/action/reward tuples from the economy)
- Resource allocation (agents with more tokens can post bigger bounties)

## Concepts

**Treasury** — System wallet with the total supply (1M tokens at genesis).
All allocations come from treasury.

**Wallet** — Every agent gets one, identified by principal ID. Call
`blockchain_my_wallet` to get yours (auto-created, 100 token starting balance).

**Transfer** — Atomic token movement between wallets. Requires sufficient balance.

**Bounty** — Posted task with escrowed tokens. Poster pays upfront. Claimer
receives tokens on completion. Double-claims rejected.

**Block** — Hash-chained container for transactions. Merkle roots for
tamper detection. Verifiable via `blockchain_verify_chain`.

## Rules

1. Fixed supply — no inflation after genesis
2. Balances always >= 0
3. Escrow is immediate and atomic
4. Chain integrity verifiable at any time
"""

WALLET_GUIDE = """# Wallet Guide

## Auto-Wallet Creation

Every MCP client gets a wallet automatically. The wallet ID is derived
from the principal ID in the envelope context:
- Kiro IDE agent: `wallet-kiro-agent`
- Strands agent: `wallet-agent-{name}`
- External client: `wallet-{principal_id}`

## Manual Creation

```
blockchain_create_wallet(owner_id="my-agent", initial_balance=100)
```

Initial balance is transferred from treasury. If treasury has insufficient
funds, creation succeeds with 0 balance.

## Checking Balance

```
blockchain_get_balance(wallet_id="wallet-my-agent")
```

## Transfers

```
blockchain_transfer(
    from_wallet="wallet-alice",
    to_wallet="wallet-bob",
    amount=50,
    memo="payment for code review"
)
```
"""

BOUNTY_GUIDE = """# Bounty Guide

Bounties are domain-agnostic tasks with escrowed tokens. The `criteria`
dict is freeform — the blockchain stores but never interprets it.

## Examples by Domain

Security: `criteria={"type": "security_scan", "target": "auth brick"}`
Code review: `criteria={"type": "code_review", "pr_number": 42}`
Documentation: `criteria={"type": "doc_update", "file": "README.md"}`
Game/RL: `criteria={"type": "connect_four", "win_condition": "beat_opponent"}`
Data: `criteria={"type": "data_label", "dataset": "images-v2", "count": 100}`

## Posting

```
blockchain_post_bounty(
    poster_wallet="wallet-alice", amount=500,
    description="Review PR #42 for correctness",
    criteria={"type": "code_review", "pr_number": 42}
)
```

## Claiming

```
blockchain_claim_bounty(bounty_id="bounty-abc123", claimer_wallet="wallet-bob")
```

## Cancelling

```
blockchain_cancel_bounty(bounty_id="bounty-abc123")
```

Escrowed tokens return to the poster.
"""

DOCS = {
    "overview": ECONOMY_OVERVIEW,
    "wallet-guide": WALLET_GUIDE,
    "bounty-guide": BOUNTY_GUIDE,
}


def get_doc(name: str) -> str | None:
    return DOCS.get(name)


def list_docs() -> list[str]:
    return list(DOCS.keys())
