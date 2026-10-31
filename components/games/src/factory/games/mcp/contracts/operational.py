"""DTOs for operational Games MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject, JsonOutput
from .deterministic import GameIdInput, GameStateOutput


class CreateGameInput(DTO):
    game_type: str = "connect_four"
    rows: int = 6
    cols: int = 7
    win_length: int = 4
    player1_name: str = "Player 1"
    player2_name: str = "Player 2"
    config: JsonObject | None = None


class MoveInput(GameIdInput):
    player: int
    column: int


class CTFMoveInput(GameIdInput):
    action: str
    command: str = ""
    path: str = ""
    content: str = ""
    flag: str = ""


class SecurityMoveInput(GameIdInput):
    action: str
    finding_type: str = ""
    location: str = ""
    finding_id: str = ""
    evidence: str = ""
    classification: str = ""


class MoveOutput(DTO):
    valid: bool
    state: GameStateOutput | None = None
    reward: dict[int, float] = {}
    terminal: bool = False
    info: JsonObject = {}
    error: str | None = None


class DeleteOutput(DTO):
    game_id: str
    deleted: bool


class ProcessFinishedInput(DTO):
    game_id: str
    game_type: str
    winner: int | None = None
    reward: dict[str, float] | None = None
    move_count: int = 0
    move_history: list[JsonObject] | None = None
    config: JsonObject | None = None
    players: dict[str, str] | None = None


class WorkflowRLInput(DTO):
    graph_id: str
    run_id: str
    vuln_class: str = ""
    domain_class: str = ""
    count_labels: list[str] | None = None
    taxonomy_edges: list[JsonObject] | None = None
    workflow_type: str = "auto"
    target_app: str = ""
    session_id: str = ""
    match_on: list[str] | None = None


class ExperimentReportInput(DTO):
    run_id: str
    workflow_type: str = "kiro"
    target_app: str = ""
    vuln_class: str = ""
    domain_class: str = ""
    count_labels: list[str] | None = None
    taxonomy_edges: list[JsonObject] | None = None
    framework: str = ""
    agent_count: int = 0
    duration_seconds: float = 0
    extra_metrics: str = "{}"


class ProcessFinishedOutput(JsonOutput):
    pass


class WorkflowRLOutput(JsonOutput):
    pass


class ExperimentReportOutput(JsonOutput):
    pass


class CreatedGameOutput(GameStateOutput):
    available: list[str] | None = None


class ResetGameOutput(GameStateOutput):
    pass
