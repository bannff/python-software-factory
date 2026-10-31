"""Game pipeline — orchestrates post-game actions across bricks.

When a game finishes, this module coordinates:
1. Graph: store game transcript as nodes/edges
2. Blockchain: claim bounty for winner (if bounty exists)
3. Evals: score the game output via Bedrock rubric
4. Memory: store learnings for next iteration (RL feedback loop)

All calls go through the MCP aggregator — no direct brick imports.
Gracefully skips any brick that's unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import normalize_correlation

logger = logging.getLogger(__name__)


def _get_invoker():
    """Get the MCP tool invoker.

    Returns None quickly if no invoker is available — never blocks.
    """
    try:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
        if invoker is not None:
            return invoker
    except Exception:
        pass
    # Skip aggregator path in standalone mode — get_server() can block
    return None


def process_game_finished(payload: dict[str, Any]) -> dict[str, Any]:
    """Process a game.finished event across bricks.

    Args:
        payload: The game.finished event payload containing
            game_id, game_type, winner, reward, move_history, etc.

    Returns:
        Summary of actions taken across bricks.
    """
    results: dict[str, Any] = {"game_id": payload.get("game_id")}
    invoker = _get_invoker()

    # 1. Store transcript in graph
    results["graph"] = _store_transcript(invoker, payload)

    # 2. Claim blockchain bounty (if applicable)
    results["blockchain"] = _claim_bounty(invoker, payload)

    # 3. Score via evals (if invoker available)
    results["evals"] = _score_output(invoker, payload)

    # 4. Store learnings in memory (RL feedback loop)
    results["memory"] = _store_learnings(invoker, payload, results)

    return results


def _store_transcript(
    invoker: Any, payload: dict[str, Any],
) -> dict[str, Any]:
    """Store game transcript as graph entities."""
    if invoker is None:
        return {"skipped": True, "reason": "no invoker"}
    try:
        game_id = payload.get("game_id", "unknown")
        game_type = payload.get("game_type", "unknown")
        correlation = normalize_correlation(payload, payload.get("config", {}), {"entity_id": f"game-{game_id}"})
        invoker("graph_graph_add_entity", entity_id=f"game-{game_id}",
                entity_type="GameSession",
            properties={"game_id": game_id, "game_type": game_type, "winner": payload.get("winner"),
                     "move_count": payload.get("move_count", 0),
                     "reward": payload.get("reward", {}),
                     "config": payload.get("config", {}),
                     **correlation})
        moves = payload.get("move_history", [])
        for i, move in enumerate(moves):
            mid = f"move-{game_id}-{i}"
            invoker("graph_graph_add_entity", entity_id=mid,
                entity_type="GameMove", properties={"step": i, "game_id": game_id, **correlation, **move})
            invoker("graph_graph_add_relationship",
                    relationship_id=f"has-move-{game_id}-{i}",
                    relationship_type="HAS_MOVE",
                    source_id=f"game-{game_id}", target_id=mid)
        logger.info("Stored transcript for game %s (%d moves)", game_id, len(moves))
        return {"stored": True, "moves": len(moves)}
    except Exception as e:
        logger.warning("Graph storage failed: %s", e)
        return {"skipped": True, "error": str(e)}


def _claim_bounty(
    invoker: Any, payload: dict[str, Any],
) -> dict[str, Any]:
    """Claim blockchain bounty if winner exists."""
    if invoker is None:
        return {"skipped": True, "reason": "no invoker"}
    winner = payload.get("winner")
    if winner is None:
        return {"skipped": True, "reason": "no winner"}
    try:
        players = payload.get("players", {})
        winner_name = players.get(winner, players.get(str(winner), f"player-{winner}"))
        wallet_id = f"wallet-{winner_name}"
        wallet_result = invoker("blockchain_get_wallet", wallet_id=wallet_id)
        wallet = getattr(wallet_result, "data", None)
        if wallet is None or not wallet.found:
            invoker("blockchain_create_wallet", owner_id=winner_name, initial_balance=0)
        reward_dict = payload.get("reward", {})
        raw = reward_dict.get(winner, reward_dict.get(str(winner), 0))
        amount = abs(raw) * 100
        if amount > 0:
            tx_result = invoker("blockchain_mint", to_wallet=wallet_id,
                                amount=amount, memo=f"game reward: {payload.get('game_id')}")
            tx = getattr(tx_result, "data", None)
            if not getattr(tx_result, "ok", False) or tx is None or not tx.success:
                return {"skipped": True, "error": getattr(tx_result, "error", None) or getattr(tx, "error", "mint_failed")}
            logger.info("Minted %.1f tokens to %s", amount, wallet_id)
            return {"claimed": True, "amount": amount, "tx": tx_result}
        return {"skipped": True, "reason": "zero reward"}
    except Exception as e:
        logger.warning("Bounty claim failed: %s", e)
        return {"skipped": True, "error": str(e)}


def _score_output(invoker: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Score game output via evals brick."""
    if invoker is None:
        return {"skipped": True, "reason": "no invoker"}
    try:
        rubric = _get_rubric(payload.get("game_type", "unknown"))
        if not rubric:
            return {"skipped": True, "reason": "no rubric for game type"}
        result = invoker(
            "evals_evaluate", evaluator_name="output", rubric=rubric,
            framework="strands",
            input_text=f"Game: {payload.get('game_type')}, Config: {payload.get('config', {})}",
            output_text=f"Moves: {payload.get('move_count', 0)}, Winner: {payload.get('winner')}, Reward: {payload.get('reward', {})}")
        return {"scored": True, "result": result}
    except Exception as e:
        logger.warning("Evals scoring failed: %s", e)
        return {"skipped": True, "error": str(e)}


def _get_rubric(game_type: str) -> str:
    """Get the evaluation rubric for a game type."""
    from .rubrics import get_rubric
    return get_rubric(game_type)


def _store_learnings(
    invoker: Any, payload: dict[str, Any],
    pipeline_results: dict[str, Any],
) -> dict[str, Any]:
    """Store learnings in memory for the RL feedback loop.

    Dual-emit tags ``[domain_class, "scan-learnings", f"{domain_class}-learnings",
    run_id]`` (bd:qer1z) ride inside ``metadata={"tags": ...}`` so they land in
    ``MemoryQuery.metadata.tags`` where ``memory_retrieve(tags=...)`` reads
    (bd:vs1vu, verdict 2efd2a40 Q9).
    """
    if invoker is None:
        return {"skipped": True, "reason": "no invoker"}
    try:
        game_type = payload.get("game_type", "unknown")
        game_id = payload.get("game_id", "unknown")
        config = payload.get("config", {})
        # bd:python-factory-qer1z back-compat: domain_class wins, vuln_class fallback.
        domain_class = config.get("domain_class") or config.get("vuln_class") or game_type
        run_id = config.get("run_id", game_id)
        reward = payload.get("reward", {})
        evals_result = pipeline_results.get("evals", {})
        moves = payload.get("move_history", [])
        submissions = [m for m in moves if m.get("action") == "submit_finding"]
        tp = sum(1 for s in submissions if s.get("move", {}).get("match") == "vulnerability")
        fp = sum(1 for s in submissions if s.get("move", {}).get("match") in ("false_positive", "none"))

        content = (
            f"Scan learnings [{domain_class}] run={run_id}: "
            f"{len(submissions)} findings submitted, {tp} TP, {fp} FP. "
            f"Reward: {reward}. "
            f"Evals: {evals_result.get('result', 'N/A')}. "
            f"Actions used: {len(moves)}."
        )
        tags = [domain_class, "scan-learnings", f"{domain_class}-learnings", run_id]
        invoker("memory_memory_store", content=content, user_id="kiro-agent",
                memory_type="long_term", category="fact", metadata={"tags": tags})
        logger.info("Stored learnings for %s run %s", domain_class, run_id)
        return {"stored": True, "content_length": len(content)}
    except Exception as e:
        logger.warning("Memory storage failed: %s", e)
        return {"skipped": True, "error": str(e)}
