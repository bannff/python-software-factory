"""Prompt templates for blockchain agent economy."""

ECONOMY_BOOTSTRAP = """# Bootstrap Agent Economy

Create wallets for {agent_count} agents with {initial_balance} tokens each.

```
blockchain_health_check()
blockchain_authoring_seed_economy(agent_count={agent_count}, initial_balance={initial_balance})
blockchain_get_chain_info()
```
"""

BOUNTY_WORKFLOW = """# Bounty Workflow

Post a bounty, wait for an agent to claim it, verify the result.

```
# 1. Post
blockchain_post_bounty(poster_wallet="{poster}", amount={amount}, description="{description}")

# 2. List open bounties
blockchain_list_bounties(status="open")

# 3. Agent claims
blockchain_claim_bounty(bounty_id="<id>", claimer_wallet="{claimer}")

# 4. Verify
blockchain_get_chain_info()
blockchain_verify_chain()
```
"""

AUDIT_TEMPLATE = """# Chain Audit

```
blockchain_get_chain_info()
blockchain_verify_chain()
blockchain_list_transactions(limit=20)
blockchain_reconcile(wallet_id="{wallet_id}")
```
"""

TEMPLATES = {
    "economy-bootstrap": ECONOMY_BOOTSTRAP,
    "bounty-workflow": BOUNTY_WORKFLOW,
    "audit": AUDIT_TEMPLATE,
}


def get_template(name: str) -> str | None:
    return TEMPLATES.get(name)


def list_templates() -> list[str]:
    return list(TEMPLATES.keys())


def render_template(name: str, **kwargs: str) -> str | None:
    template = TEMPLATES.get(name)
    if template is None:
        return None
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
