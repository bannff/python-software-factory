"""Which game types a person can actually play from the UI.

The security scenarios (ctf, sql_injection, finding_triage, ...) are created as
empty shells: their challenge data is supplied by an agent or workflow run, so a
person who starts one from a picker gets nothing to play or score. Only types
that are complete on creation are listed here.
"""
from __future__ import annotations

HUMAN_PLAYABLE_GAME_TYPES: tuple[str, ...] = ("connect_four",)
