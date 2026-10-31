## Purpose

Provides a deployable Polylith base that composes OpenArcade's control-plane
bricks (`launch`, `library`, `arcade_config`, `state`, `curator`) and the Flet
UI shell into a single installable unit with a stable Python entry point, a
Typer CLI, and a documented environment-variable contract.

## ADDED Requirements

### Requirement: Base is installable as a single Python distribution
The system SHALL provide a `bases/openarcade/` Polylith base whose
`pyproject.toml` declares the lean runtime dependency set
(`flet`, `pydantic`, `structlog`, `typer`, `pyyaml`) and whose `BRICK.yaml`
declares `type: base` with `namespace: factory.openarcade`. The base MUST
be discoverable by `poly info` / `foreman info` alongside the other bases
in the monorepo.

#### Scenario: Base shows up in workspace inventory
- **WHEN** an operator runs `foreman info` from the monorepo root
- **THEN** the output lists `factory.openarcade` with `type: base` and
  enumerates `launch`, `library`, `arcade_config`, `state`, `curator`,
  and `ui` as consumed bricks

#### Scenario: Base installs in a clean venv
- **WHEN** an operator creates a fresh virtualenv and runs
  `pip install -e bases/openarcade` followed by the wall entry point
- **THEN** the wall UI launches without `ModuleNotFoundError` for any
  control-plane brick or for the `ui` Flet adapter

### Requirement: Stable public Python API
The base MUST expose a stable import surface at `factory.openarcade`
with at minimum: `build_app(config_dir)`, `run_wall(config_dir)`,
`NciTransport`, `GetStatusProbe`, and a re-export of the wall's public
view-model types (`GameTile`, `ControlsVM`).

#### Scenario: Importing the public surface
- **WHEN** a downstream caller writes
  `from factory.openarcade import build_app, run_wall, NciTransport, GetStatusProbe`
- **THEN** the import succeeds and the symbols resolve to the wall's
  real implementations without requiring any `sys.path` manipulation

#### Scenario: Public surface is lean
- **WHEN** the base is imported
- **THEN** the `fastmcp` package is NOT transitively imported (the
  control-plane bricks' MCP-surface modules stay unreachable from the
  lean import path)

### Requirement: Typer CLI for headless use
The base MUST provide a Typer CLI exposing `openarcade run`,
`openarcade scan`, and `openarcade launch <game-id>`. The CLI MUST
accept `--config-dir`, `--nci-host`, and `--nci-port` flags and MUST
read the same environment variables as the GUI when flags are absent.

#### Scenario: Running the wall headlessly
- **WHEN** an operator runs `openarcade run --config-dir ./openarcade_config`
  in a terminal
- **THEN** the wall UI launches with that config dir, with the
  existing keyboard navigation and detail pages behaving identically
  to launching via the `wall/` entry point

#### Scenario: Scanning a ROM directory
- **WHEN** an operator runs
  `openarcade scan /path/to/roms --config-dir ./openarcade_config`
- **THEN** the CLI prints a JSON summary of detected
  `RomCandidate` records (path, system, sha1, size) and persists a
  scan report under the config dir, without launching the wall UI

#### Scenario: Launching a single game
- **WHEN** an operator runs
  `openarcade launch contra --config-dir ./openarcade_config`
- **THEN** the CLI sends the launch command via the configured
  `NciTransport`, polls `GetStatusProbe` until ready (or 5 s
  timeout), and exits 0 on `PLAYING` or 1 on timeout

### Requirement: Documented environment-variable contract
The base MUST document and respect three environment variables:
`OPENARCADE_CONFIG_DIR` (override the default config dir),
`OPENARCADE_NCI_HOST` (override the NCI UDP target host, default
`127.0.0.1`), and `OPENARCADE_NCI_PORT` (override the NCI UDP target
port, default `55355`). The default config dir MUST be `./openarcade_config`
relative to the working directory; the base MUST NOT call
`Path.home()` or `expanduser()` to resolve it.

#### Scenario: Config dir resolution priority
- **WHEN** the wall launches and the operator sets
  `OPENARCADE_CONFIG_DIR=/tmp/oa-test` in the environment
- **THEN** the base writes and reads config under `/tmp/oa-test` and
  never touches `~/.config/retroarch` or any user-home path

#### Scenario: NCI target override
- **WHEN** the operator sets
  `OPENARCADE_NCI_HOST=10.0.0.42 OPENARCADE_NCI_PORT=6000` and clicks
  Play on a tile
- **THEN** the launch command is sent to `10.0.0.42:6000` and the
  `GetStatusProbe` polls the same address

#### Scenario: No home-directory writes
- **WHEN** the base writes any config file
- **THEN** the resolved path is either the explicit `--config-dir`,
  the `OPENARCADE_CONFIG_DIR` env value, or the CWD-relative default
  — never a path under the operator's `$HOME`

### Requirement: Composition is auditable
The base MUST declare, in `BRICK.yaml`, the list of bricks it
wires. The base's source code MUST NOT import from any brick that
is not declared in `BRICK.yaml`. A CI guard MUST fail the build
when a source import references an undeclared brick, naming the
undeclared brick in the error message.

#### Scenario: Undeclared brick import fails the build
- **WHEN** a maintainer adds `from factory.<new_brick> import X`
  to the base's source without adding `<new_brick>` to the
  declared-brick list in `BRICK.yaml`
- **THEN** the CI build fails with an error message that names
  `<new_brick>` as the undeclared brick, with no need to manually
  run any resolve-deps command

#### Scenario: Declared-brick list is the audit trail
- **WHEN** an operator reads `bases/openarcade/BRICK.yaml`
- **THEN** the declared-brick list names every brick the base
  imports from, in declaration order, matching the import order
  in `bases/openarcade/src/factory/openarcade/app.py`

### Requirement: Backward-compatible shell entry points
The existing `projects/openarcade/run.sh` and `run_web.sh` shell
scripts MUST continue to work after the base is introduced. They
MUST become thin wrappers that set the same env vars and delegate to
`python -m factory.openarcade` so existing CI / human workflows
don't break.

#### Scenario: Legacy run.sh still launches the wall
- **WHEN** an operator runs `./projects/openarcade/run.sh` after the
  base lands
- **THEN** the wall UI launches identically to the pre-base
  behavior, with the same `PYTHONPATH`, env defaults, and
  `OPENARCADE_CONFIG_DIR` semantics
