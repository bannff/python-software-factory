"""Navigation grouping logic for sidebar rendering.

Maps bricks to domain categories for grouped sidebar navigation.
This presentation concern belongs in the ui brick's adapter layer,
not in the dashboard base (which must remain a pure transport shell
with zero hardcoded brick knowledge).
"""

from __future__ import annotations

# Domain groupings — views are grouped by their brick's domain.
# Bricks not listed here fall into "Other".
DOMAIN_MAP: dict[str, list[str]] = {
    "AI & Agents": ["agent", "memory", "kb", "llm_gateway",
                     "machine_learning"],
    "Data & Storage": ["cache", "storage", "graph"],
    "Security": ["auth", "security", "permissions"],
    "Observability": ["telemetry", "evals", "events", "logger"],
    "Infrastructure": ["integrations", "workflow", "api", "http",
                        "mcp_server", "config", "notification",
                        "browser", "sandbox", "hardware", "worker"],
    "Commerce": ["payments", "blockchain"],
    "Platform": ["blueprint", "dashboard", "ui", "test"],
    "Fun": ["games"],
}

# Reverse lookup: brick → domain
BRICK_DOMAIN: dict[str, str] = {
    brick: domain
    for domain, bricks in DOMAIN_MAP.items()
    for brick in bricks
}

# Canonical display order for domains.
DOMAIN_ORDER: list[str] = list(DOMAIN_MAP.keys()) + ["Other"]


def brick_domain(brick_name: str) -> str:
    """Return the domain label for a brick, defaulting to 'Other'."""
    return BRICK_DOMAIN.get(brick_name, "Other")


def group_by_domain(
    nav_views: list[dict],
    browse_bricks: list[str],
) -> tuple[dict[str, list[dict]], dict[str, list[str]], list[str]]:
    """Group views and browse-only bricks by domain.

    Returns:
        (grouped_views, grouped_bricks, ordered_domains)
    """
    grouped: dict[str, list[dict]] = {}
    for v in nav_views:
        domain = brick_domain(v.get("brick", ""))
        grouped.setdefault(domain, []).append(v)

    browse_grouped: dict[str, list[str]] = {}
    for b in browse_bricks:
        domain = brick_domain(b)
        browse_grouped.setdefault(domain, []).append(b)

    seen: set[str] = set()
    ordered: list[str] = []
    for d in DOMAIN_ORDER:
        if d not in seen and (d in grouped or d in browse_grouped):
            ordered.append(d)
            seen.add(d)

    return grouped, browse_grouped, ordered
