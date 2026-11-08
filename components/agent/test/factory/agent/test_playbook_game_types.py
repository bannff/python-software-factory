"""Playbooks may only instruct game types the games brick actually registers (#383)."""
from __future__ import annotations

import re

from factory.agent.registry import redteam_eval_playbooks as playbooks
from factory.games.runtime.runtime import GamesRuntime

_CREATE = re.compile(r"games_create\(game_type='([a-z_]+)'")


def test_every_playbook_game_type_is_registered():
    prompts = [v for v in vars(playbooks).values() if isinstance(v, str)]
    used = {m for p in prompts for m in _CREATE.findall(p)}
    assert used, "playbooks should reference at least one games_create call"
    assert used <= set(GamesRuntime.available_game_types())
