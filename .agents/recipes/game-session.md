# Recipe: Game Session

Validates the game engine, session management, and telemetry integration.

## Bricks Used
- `games` - Turn-based game engine (Connect Four, security games)
- `telemetry` - Distributed tracing for game events
- `events` - Event streaming for game state changes

## Scenario

Create a Connect Four game, play several moves, track game events, and trace the session with telemetry.

## Prerequisites

- No AWS required
- All bricks use memory adapters

## Steps

### Step 1: Initialize Bricks

```python
import tempfile
from pathlib import Path
import yaml

# Games
from factory.games.runtime.runtime import GamesRuntime
games = GamesRuntime()

# Events
tmpdir_events = Path(tempfile.mkdtemp())
(tmpdir_events / "subscriptions").mkdir(parents=True, exist_ok=True)
from factory.events.runtime.runtime import EventsRuntime
events = EventsRuntime(config_dir=tmpdir_events)

# Telemetry
tmpdir_tel = Path(tempfile.mkdtemp())
(tmpdir_tel / "exporters").mkdir(parents=True, exist_ok=True)
(tmpdir_tel / "metrics").mkdir(parents=True, exist_ok=True)
(tmpdir_tel / "settings.yaml").write_text(yaml.safe_dump({
    "schema_version": 1,
    "service": {"name": "recipe-game-session", "version": "1.0.0"},
    "otel": {"enabled": True, "tracing_enabled": True, "metrics_enabled": True, "logging_enabled": False},
}))
from factory.telemetry.runtime.runtime import TelemetryRuntime
telemetry = TelemetryRuntime(config_dir=tmpdir_tel)
telemetry.initialize()
```

### Step 2: Health Checks

```python
health = games.health_check()
# Returns: {"healthy": True, "backend": "memory", "active_games": 0}

available = games.available_game_types()
# Returns: ["connect_four"]
```

### Step 3: Start Telemetry Span

```python
span = telemetry.start_span(
    name="game-session",
    attributes={"game_type": "connect_four", "recipe": "game-session"},
)
span_id = span.get("span_id")
```

### Step 4: Create Game

```python
state = games.create_game(
    game_type="connect_four",
    player_names={1: "Alice", 2: "Bob"},
)
game_id = state.game_id
# state.status == "active", state.current_player == 1
```

### Step 5: Publish Game Created Event

```python
event = events.publish(
    event_type="game.created",
    payload={"game_id": game_id, "game_type": "connect_four", "players": state.players},
    source="games-brick",
)
# Returns: EventResult(event_id="...", status="published")
```

### Step 6: Play Moves

```python
# Player 1 (Alice) drops in column 3
result = games.make_move(game_id, player=1, move={"column": 3})
# Returns: MoveResult(valid=True, state=GameState(...))

# Player 2 (Bob) drops in column 4
result = games.make_move(game_id, player=2, move={"column": 4})

# Player 1 drops in column 3 again
result = games.make_move(game_id, player=1, move={"column": 3})

# Check legal moves
legal = games.legal_moves(game_id)
# Returns: list of {"column": N} dicts for available columns
```

### Step 7: Evaluate Board Position

```python
evaluation = games.evaluate(game_id)
# Returns: heuristic evaluation dict for RL reward shaping
```

### Step 8: Verify Game State

```python
state = games.get_game(game_id)
# state.move_history has 3 entries
# state.current_player == 2 (Bob's turn)

all_games = games.list_games(status="active")
# Returns: list with our game
```

### Step 9: End Telemetry Span

```python
telemetry.end_span(span_id=span_id, error=None)
```

## Success Criteria

- [x] Game created with correct initial state
- [x] Moves applied correctly, turns alternate
- [x] Legal moves returned for current position
- [x] Board evaluation works for RL
- [x] Game events published
- [x] Telemetry span tracks session

## Security Game Session

Security games use `games_create` with a `config` dict containing `ground_truth` and game-specific settings, then `games_security_move` for structured vulnerability-hunting actions.

### Step 1: Create a Security Game

```python
state = games.create_game(
    game_type="sql_injection",
    player_names={1: "security-agent"},
    config={
        "ground_truth": {
            "vulnerabilities": [
                {"type": "sqli", "location": "/api/users?id=", "severity": "high"},
            ],
        },
        "max_actions": 20,
        "target_url": "http://localhost:5050",
    },
)
game_id = state.game_id
```

### Step 2: Play with `games_security_move`

The `games_security_move` tool supports six actions:

| Action | Purpose |
|--------|---------|
| `analyze_code` | Static analysis of a source file |
| `trace_dataflow` | Follow data from source to sink |
| `submit_finding` | Report a discovered vulnerability |
| `check_config` | Inspect application configuration |
| `test_endpoint` | Probe a live endpoint |
| `read_file` | Read a file from the target |

```python
# Analyze a source file
move = games.security_move(game_id, action="analyze_code", location="/app/routes/users.py")

# Trace data flow through the code
move = games.security_move(game_id, action="trace_dataflow", location="/app/routes/users.py")

# Submit a finding
move = games.security_move(
    game_id,
    action="submit_finding",
    finding_type="sqli",
    location="/api/users?id=",
    evidence="User input concatenated into SQL query without parameterization",
    classification="high",
)
# move.reward reflects ground_truth match accuracy
```

### Step 3: Verify Results

```python
state = games.get_game(game_id)
# state.move_history tracks all security actions
# state.status == "finished" once max_actions reached or all vulns found
```

### Available Security Game Adapters

`sql_injection`, `xss_hunter`, `command_injection`, `ssti`, `idor_detective`, `path_traversal`, `finding_triage`

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| games | `factory.games.runtime.runtime.GamesRuntime` | `create_game()`, `make_move()`, `legal_moves()`, `evaluate()`, `security_move()` |
| games | `factory.games.runtime.ports` | `GameState`, `MoveResult`, `GameRules` |

## MCP Tools

| Tool | Category | Description |
|------|----------|-------------|
| `games_create` | operational | Create game session (accepts optional `config` dict for security games: ground_truth, max_actions, etc.) |
| `games_move` | operational | Make a move |
| `games_security_move` | operational | Security game move (analyze_code, trace_dataflow, submit_finding, check_config, test_endpoint, read_file) |
| `telemetry_start_span` | operational | Start a telemetry span |
| `telemetry_end_span` | operational | End a telemetry span |
| `events_publish` | operational | Publish an event |
