"""Typed operational MCP tools for Games."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from factory.mcp_utils.interface import ToolResult, make_serializable, operational

from .contracts.deterministic import GameIdInput
from .contracts.operational import (
    CTFMoveInput, CreateGameInput, CreatedGameOutput, DeleteOutput,
    ExperimentReportInput, ExperimentReportOutput, MoveInput, MoveOutput,
    ProcessFinishedInput, ProcessFinishedOutput, ResetGameOutput, SecurityMoveInput,
    WorkflowRLInput, WorkflowRLOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import GamesRuntime


def _move_result(result: Any) -> dict[str, Any]:
    if not result.valid:
        return {"valid": False, "error": result.error}
    return {"valid": True, "state": result.state.to_dict() if result.state else None,
            "reward": result.reward, "terminal": result.terminal, "info": result.info}


def register(mcp: Any, get_runtime: Callable[[], "GamesRuntime"]) -> None:
    """Register operational tools with strict public contracts."""

    @mcp.tool()
    @operational(input_model=CreateGameInput, output_model=CreatedGameOutput)
    def games_create(game_type: str = "connect_four", rows: int = 6, cols: int = 7,
                     win_length: int = 4, player1_name: str = "Player 1",
                     player2_name: str = "Player 2", config: dict[str, Any] | None = None) -> ToolResult[CreatedGameOutput]:
        runtime = get_runtime()
        available = runtime.available_game_types()
        if game_type not in available:
            return {
                "game_id": "", "game_type": game_type, "board": [], "current_player": 0,
                "status": "", "move_history": [], "players": {}, "config": {},
                "created_at": "", "updated_at": "", "move_count": 0,
                "error": "unknown_game_type", "available": available,
            }
        game_config = config or {}
        if game_type == "connect_four":
            game_config.setdefault("rows", rows); game_config.setdefault("cols", cols)
            game_config.setdefault("win_length", win_length)
        return make_serializable(runtime.create_game(game_type, game_config, {1: player1_name, 2: player2_name}).to_dict())

    @mcp.tool()
    @operational(input_model=MoveInput, output_model=MoveOutput)
    def games_move(game_id: str, player: int, column: int) -> ToolResult[MoveOutput]:
        return make_serializable(_move_result(get_runtime().make_move(game_id, player, {"column": column})))

    @mcp.tool()
    @operational(input_model=GameIdInput, output_model=DeleteOutput)
    def games_delete(game_id: str) -> ToolResult[DeleteOutput]:
        return {"game_id": game_id, "deleted": get_runtime().get_store().delete(game_id)}

    @mcp.tool()
    @operational(input_model=GameIdInput, output_model=ResetGameOutput)
    def games_reset(game_id: str) -> ToolResult[ResetGameOutput]:
        runtime = get_runtime(); old = runtime.get_game(game_id)
        if old is None:
            return {"game_id": game_id, "game_type": "", "board": [], "current_player": 0,
                    "status": "", "move_history": [], "players": {}, "config": {},
                    "created_at": "", "updated_at": "", "move_count": 0,
                    "error": f"Game {game_id} not found"}
        state = runtime.get_rules(old.game_type).create_initial_state(game_id, old.config)
        state.players = old.players; runtime.get_store().save(state)
        return make_serializable(state.to_dict())

    @mcp.tool()
    @operational(input_model=CTFMoveInput, output_model=MoveOutput)
    def games_ctf_move(game_id: str, action: str, command: str = "", path: str = "",
                       content: str = "", flag: str = "") -> ToolResult[MoveOutput]:
        move = {"action": action, **{key: value for key, value in
                (("command", command), ("path", path), ("content", content), ("flag", flag)) if value}}
        return make_serializable(_move_result(get_runtime().make_move(game_id, 1, move)))

    @mcp.tool()
    @operational(input_model=SecurityMoveInput, output_model=MoveOutput)
    def games_security_move(game_id: str, action: str, finding_type: str = "", location: str = "",
                            finding_id: str = "", evidence: str = "", classification: str = "") -> ToolResult[MoveOutput]:
        move = {"action": action, **{key: value for key, value in
                (("type", finding_type), ("location", location), ("finding_id", finding_id),
                 ("evidence", evidence), ("classification", classification)) if value}}
        return make_serializable(_move_result(get_runtime().make_move(game_id, 1, move)))

    @mcp.tool()
    @operational(input_model=ProcessFinishedInput, output_model=ProcessFinishedOutput)
    def games_process_finished(game_id: str, game_type: str, winner: int | None = None,
                               reward: dict[str, float] | None = None, move_count: int = 0,
                               move_history: list[dict[str, Any]] | None = None,
                               config: dict[str, Any] | None = None, players: dict[str, str] | None = None) -> ToolResult[ProcessFinishedOutput]:
        from ..runtime.game_pipeline import process_game_finished
        try:
            return make_serializable(process_game_finished({"game_id": game_id, "game_type": game_type,
                "winner": winner, "reward": reward or {}, "move_count": move_count,
                "move_history": move_history or [], "config": config or {}, "players": players or {}}))
        except Exception as error:
            return make_serializable({"error": str(error)})

    @mcp.tool()
    @operational(input_model=WorkflowRLInput, output_model=WorkflowRLOutput)
    def games_process_workflow_rl(graph_id: str, run_id: str, vuln_class: str = "", domain_class: str = "",
                                  count_labels: list[str] | None = None, taxonomy_edges: list[dict] | None = None,
                                  workflow_type: str = "auto", target_app: str = "", session_id: str = "",
                                  match_on: list[str] | None = None) -> ToolResult[WorkflowRLOutput]:
        from ..runtime.workflow_rl import process_workflow_rl
        return make_serializable(process_workflow_rl(graph_id=graph_id, run_id=run_id, vuln_class=vuln_class,
            domain_class=domain_class, count_labels=count_labels, taxonomy_edges=taxonomy_edges,
            workflow_type=workflow_type, target_app=target_app, session_id=session_id, match_on=match_on))

    @mcp.tool()
    @operational(input_model=ExperimentReportInput, output_model=ExperimentReportOutput)
    def games_write_experiment_report(run_id: str, workflow_type: str = "kiro", target_app: str = "",
                                      vuln_class: str = "", domain_class: str = "", count_labels: list[str] | None = None,
                                      taxonomy_edges: list[dict] | None = None, framework: str = "", agent_count: int = 0,
                                      duration_seconds: float = 0, extra_metrics: str = "{}") -> ToolResult[ExperimentReportOutput]:
        import json
        from ..runtime.workflow_report import write_experiment_report
        from ..runtime.workflow_rl import process_workflow_rl
        report = process_workflow_rl(graph_id=f"{workflow_type}-{vuln_class.lower()}", run_id=run_id,
            vuln_class=vuln_class, domain_class=domain_class, count_labels=count_labels,
            taxonomy_edges=taxonomy_edges, workflow_type=workflow_type or "workflow", target_app=target_app,
            emit_lifecycle=False)
        return make_serializable(write_experiment_report(rl_report=report, run_id=run_id,
            workflow_type=workflow_type, target_app=target_app, vuln_class=vuln_class, domain_class=domain_class,
            count_labels=count_labels, taxonomy_edges=taxonomy_edges, framework=framework,
            agent_count=agent_count, duration_seconds=duration_seconds,
            extra_metrics=json.loads(extra_metrics) if extra_metrics else {}))
