"""Path management for authoring operations."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AuthoringPaths:
    """Paths for authoring operations scoped to a config directory."""
    
    root: Path

    @property
    def agents_dir(self) -> Path:
        return self.root / "agents"

    @property
    def swarms_dir(self) -> Path:
        return self.root / "swarms"

    @property
    def graphs_dir(self) -> Path:
        return self.root / "graphs"

    @property
    def squads_dir(self) -> Path:
        return self.root / "squads"

    @property
    def tools_dir(self) -> Path:
        return self.root / "tools"

    @property
    def settings_file(self) -> Path:
        return self.root / "settings.yaml"
