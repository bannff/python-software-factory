"""Action form builder for Agent Economy dashboard.

Exports:
- economy_action_form(): collapsible card with wallet/transfer/bounty actions

Split from views.py to stay under 200 LOC per file.
"""

from __future__ import annotations

from typing import Any


def economy_action_form() -> dict[str, Any]:
    """Collapsible card with wallet creation and action pane."""
    return {
        "id": "bc-actions-card",
        "type": "card",
        "props": {
            "title": "Economy Actions",
            "icon": "💳",
            "collapsible": True,
        },
        "children": [
            {
                "id": "bc-create-form",
                "type": "form",
                "props": {
                    "tool": "blockchain_create_wallet",
                    "title": "Create Wallet",
                    "submit_label": "Create Wallet",
                    "fields": [
                        {
                            "name": "owner_id",
                            "label": "Owner ID",
                            "type": "text",
                            "placeholder": "agent-007",
                            "tooltip": "Unique identifier for the owner",
                        },
                        {
                            "name": "initial_balance",
                            "label": "Initial Balance",
                            "type": "number",
                            "min": 0, "value": 0,
                            "tooltip": "Starting token balance",
                        },
                    ],
                },
            },
            {
                "id": "bc-action-pane",
                "type": "action_pane",
                "props": {
                    "actions": _actions(),
                    "default_action": "transfer",
                },
            },
        ],
    }


def _actions() -> list[dict[str, Any]]:
    """Write-operation actions for the economy action pane."""
    return [
        {
            "id": "transfer", "label": "Transfer Tokens", "icon": "💸",
            "tool": "blockchain_transfer",
            "submit_label": "Send Tokens",
            "fields": [
                {"name": "from_wallet", "label": "From Wallet",
                 "type": "text", "placeholder": "wallet-abc",
                 "tooltip": "Source wallet ID"},
                {"name": "to_wallet", "label": "To Wallet",
                 "type": "text", "placeholder": "wallet-xyz",
                 "tooltip": "Destination wallet ID"},
                {"name": "amount", "label": "Amount",
                 "type": "number", "min": 0, "placeholder": "100",
                 "tooltip": "Number of tokens to transfer"},
                {"name": "memo", "label": "Memo", "type": "text",
                 "placeholder": "Payment for task completion",
                 "tooltip": "Optional transaction note"},
            ],
        },
        {
            "id": "post-bounty", "label": "Post Bounty", "icon": "🏆",
            "tool": "blockchain_post_bounty",
            "submit_label": "Post Bounty",
            "fields": [
                {"name": "poster_wallet", "label": "Poster Wallet",
                 "type": "text", "placeholder": "wallet-abc",
                 "tooltip": "Wallet that funds the bounty escrow"},
                {"name": "amount", "label": "Reward Amount",
                 "type": "number", "min": 1, "placeholder": "500",
                 "tooltip": "Tokens escrowed as bounty reward"},
                {"name": "description", "label": "Description",
                 "type": "textarea",
                 "placeholder": "Complete security audit",
                 "tooltip": "What the bounty requires"},
            ],
        },
        {
            "id": "claim-bounty", "label": "Claim Bounty", "icon": "🎯",
            "tool": "blockchain_claim_bounty",
            "submit_label": "Claim",
            "fields": [
                {"name": "bounty_id", "label": "Bounty ID",
                 "type": "text", "placeholder": "bounty-123",
                 "tooltip": "ID of the bounty to claim"},
                {"name": "claimer_wallet", "label": "Claimer Wallet",
                 "type": "text", "placeholder": "wallet-xyz",
                 "tooltip": "Wallet to receive the reward"},
            ],
        },
        {
            "id": "mint-tokens", "label": "Mint Tokens", "icon": "🪙",
            "tool": "blockchain_mint",
            "submit_label": "Mint",
            "fields": [
                {"name": "to_wallet", "label": "To Wallet",
                 "type": "text", "placeholder": "wallet-abc",
                 "tooltip": "Wallet to receive minted tokens"},
                {"name": "amount", "label": "Amount",
                 "type": "number", "min": 1, "placeholder": "1000",
                 "tooltip": "Number of new tokens to mint"},
                {"name": "memo", "label": "Memo", "type": "text",
                 "placeholder": "Treasury allocation Q1",
                 "tooltip": "Optional mint memo"},
            ],
        },
    ]
