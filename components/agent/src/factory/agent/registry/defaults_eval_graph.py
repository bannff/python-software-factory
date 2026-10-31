"""Standalone eval/RL graph — triggered after any workflow completes.

Each swarm has 6 agents (one per model family) with team rosters.
"""
from __future__ import annotations

from .redteam_eval_playbooks import (
    REVIEW_GAME_MASTER, REVIEW_EVAL_JUDGE,
    LEARN_SYNTHESIZER, LEARN_MEMORY_CURATOR,
)
from .models import HAIKU, SONNET, NOVA2_LITE, SCOUT, MAVERICK, GPT_OSS

_REVIEW_ROSTER = (
    "\n\nYOUR TEAM (hand off to each in order):\n"
    "1. game-master — creates game sessions, records moves\n"
    "2. eval-judge — runs LLMAJ evaluators, scores output\n"
    "3. review-scout — independent eval, cross-checks scores\n"
    "4. review-maverick — deep-dives on tool selection quality\n"
    "5. review-nova — checks goal success and trajectory\n"
    "6. score-calibrator — final calibration, stores summary\n"
    "After YOUR work, hand off to the next agent who hasn't gone."
)

_LEARN_ROSTER = (
    "\n\nYOUR TEAM (hand off to each in order):\n"
    "1. learning-synthesizer — extracts learnings from scores\n"
    "2. memory-curator — consolidates and deduplicates memories\n"
    "3. learn-scout — independent learning extraction\n"
    "4. learn-maverick — identifies improvement patterns\n"
    "5. learn-haiku — issues blockchain rewards for high scores\n"
    "6. reward-issuer — final rewards + iteration metrics\n"
    "After YOUR work, hand off to the next agent who hasn't gone."
)

_R_SCOUT = "\n\nYou are review-scout. Run independent evals on findings others missed."
_R_MAV = "\n\nYou are review-maverick. Deep-dive on tool_selection and tool_parameter evals."
_R_NOVA = "\n\nYou are review-nova. Focus on goal_success and trajectory evaluators."
_R_CAL = "\n\nYou are score-calibrator (final). Cross-check all scores. Store REVIEW SUMMARY."

_L_SCOUT = "\n\nYou are learn-scout. Extract learnings from areas others missed."
_L_MAV = "\n\nYou are learn-maverick. Identify recurring improvement patterns across runs."
_L_HAIKU = "\n\nYou are learn-haiku. Issue blockchain rewards for scores >0.7."
_L_REWARD = "\n\nYou are reward-issuer (final). Final rewards + metrics. Store LEARN SUMMARY."

REVIEW_SWARM: dict = {
    "id": "eval-review",
    "name": "Eval Review Swarm",
    "description": "Review workflow results, create games, score with LLMAJ.",
    "entry_point": "game-master",
    "max_handoffs": 20,
    "max_iterations": 40,
    "agents": [
        {"id": "game-master", "model": "",
         "system_prompt": REVIEW_GAME_MASTER + _REVIEW_ROSTER, "tools": []},
        {"id": "eval-judge", "model": "",
         "system_prompt": REVIEW_EVAL_JUDGE + _REVIEW_ROSTER, "tools": []},
        {"id": "review-scout", "model": "",
         "system_prompt": REVIEW_GAME_MASTER + _REVIEW_ROSTER + _R_SCOUT, "tools": []},
        {"id": "review-maverick", "model": "",
         "system_prompt": REVIEW_EVAL_JUDGE + _REVIEW_ROSTER + _R_MAV, "tools": []},
        {"id": "review-nova", "model": "",
         "system_prompt": REVIEW_GAME_MASTER + _REVIEW_ROSTER + _R_NOVA, "tools": []},
        {"id": "score-calibrator", "model": "",
         "system_prompt": REVIEW_EVAL_JUDGE + _REVIEW_ROSTER + _R_CAL, "tools": []},
    ],
}

LEARN_SWARM: dict = {
    "id": "eval-learn",
    "name": "Eval Learn Swarm",
    "description": "Synthesize learnings, issue rewards, curate memory.",
    "entry_point": "learning-synthesizer",
    "max_handoffs": 20,
    "max_iterations": 40,
    "agents": [
        {"id": "learning-synthesizer", "model": "",
         "system_prompt": LEARN_SYNTHESIZER + _LEARN_ROSTER, "tools": []},
        {"id": "memory-curator", "model": "",
         "system_prompt": LEARN_MEMORY_CURATOR + _LEARN_ROSTER, "tools": []},
        {"id": "learn-scout", "model": "",
         "system_prompt": LEARN_SYNTHESIZER + _LEARN_ROSTER + _L_SCOUT, "tools": []},
        {"id": "learn-maverick", "model": "",
         "system_prompt": LEARN_MEMORY_CURATOR + _LEARN_ROSTER + _L_MAV, "tools": []},
        {"id": "learn-haiku", "model": "",
         "system_prompt": LEARN_SYNTHESIZER + _LEARN_ROSTER + _L_HAIKU, "tools": []},
        {"id": "reward-issuer", "model": "",
         "system_prompt": LEARN_SYNTHESIZER + _LEARN_ROSTER + _L_REWARD, "tools": []},
    ],
}

EVAL_SWARMS: list[dict] = [REVIEW_SWARM, LEARN_SWARM]

EVAL_RL_GRAPH: dict = {
    "id": "eval-rl-feedback",
    "name": "Eval/RL Feedback Graph",
    "description": "Standalone feedback graph: review → learn.",
    "entry_point": "review",
    "nodes": [
        {"id": "review", "type": "swarm", "swarm_id": "eval-review",
         "description": "Review results, create games, score with LLMAJ"},
        {"id": "learn", "type": "swarm", "swarm_id": "eval-learn",
         "description": "Synthesize learnings, issue rewards, curate memory"},
    ],
    "edges": [{"source": "review", "target": "learn"}],
    "max_cycles": 1,
}

EVAL_GRAPHS: list[dict] = [EVAL_RL_GRAPH]
