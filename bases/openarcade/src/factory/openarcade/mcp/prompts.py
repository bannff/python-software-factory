"""MCP prompts for openarcade — structured payloads agents can act on.

FastMCP 3.x prompts must return ``str`` (or ``Message``/``PromptResult``
objects). We return JSON-encoded dicts so downstream agents can deserialize
the structured payload without coupling to Python types.
"""

from __future__ import annotations

import json
from typing import Any, Callable


from ..runtime import OpenArcadeRuntime


def register(mcp: Any, get_runtime: Callable[[], OpenArcadeRuntime]) -> None:

    @mcp.prompt(name="play_game")
    def play_game(game_id: str) -> str:
        """Return the JSON-encoded launch payload for ``openarcade_launch``."""
        runtime = get_runtime()
        return json.dumps(
            {
                "game_id": game_id,
                "action": "launch",
                "via": "openarcade_launch",
                "args": {
                    "game_id": game_id,
                    "nci_host": runtime.nci_host,
                    "nci_port": runtime.nci_port,
                    "timeout": 5.0,
                },
                "expected_state": "PLAYING",
            },
            indent=2,
            sort_keys=True,
        )

    @mcp.prompt(name="scan_rom_directory")
    def scan_rom_directory(rom_dir: str) -> str:
        """Return the JSON-encoded scan payload for ``openarcade_scan_roms``."""
        return json.dumps(
            {
                "rom_dir": rom_dir,
                "action": "scan",
                "via": "openarcade_scan_roms",
                "args": {"rom_dir": rom_dir},
                "expected_fields": ["count", "candidates", "report_path"],
            },
            indent=2,
            sort_keys=True,
        )


__all__ = ["register"]
