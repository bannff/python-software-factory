"""Pydantic models for games brick configuration."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GamesSettings(BaseModel):
    """Configuration for the games runtime."""
    default_game_type: str = Field(default="connect_four")
    store_backend: str = Field(default="memory")
    max_active_games: int = Field(default=100)
