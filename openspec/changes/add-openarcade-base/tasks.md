## 1. Scaffold the base directory

- [ ] 1.1 Create `bases/openarcade/` with `BRICK.yaml`, `pyproject.toml`, `src/`, and `test/` subdirs
- [ ] 1.2 Write `BRICK.yaml` with `type: base`, `namespace: factory.openarcade`, and a project-local `declared-bricks: [launch, library, arcade_config, state, curator, ui]` list plus the `flet_adapter` feature flag. Note in a `#` comment that this is a project-local convention, not a Polylith-standard field
- [ ] 1.3 Write `pyproject.toml` declaring the lean runtime set (`flet`, `pydantic`, `structlog`, `typer`, `pyyaml`) and the brick source paths under `[tool.polylith.bricks]`
- [ ] 1.4 Run `foreman info` and confirm `factory.openarcade` is listed as a base alongside the existing seven

## 2. Public Python API

- [ ] 2.1 Create `src/factory/openarcade/__init__.py` re-exporting `build_app`, `run_wall`, `NciTransport`, `GetStatusProbe`, `GameTile`, `ControlsVM`
- [ ] 2.2 Create `src/factory/openarcade/app.py` implementing `build_app(config_dir) -> ft.App` and `run_wall(config_dir=None)` using the `wall.navigator` + `wall.fixtures` + `wall.config_service` + `wall.curator_bridge` against the control-plane bricks' `runtime` modules (NOT `interface`)
- [ ] 2.3 Add a `__main__.py` so `python -m factory.openarcade` runs the wall with the same env semantics as the CLI's `run` subcommand
- [ ] 2.4 Verify lean import: importing `factory.openarcade` in a clean venv does NOT import `fastmcp` (write a small assertion test that greps `sys.modules`)

## 3. Typer CLI

- [ ] 3.1 Create `src/factory/openarcade/cli.py` with a Typer app exposing `run`, `scan`, and `launch` subcommands
- [ ] 3.2 Implement `openarcade run --config-dir <path> --nci-host <h> --nci-port <p>` that calls `run_wall(config_dir)` and resolves env vars when flags are absent
- [ ] 3.3 Implement `openarcade scan <rom-dir> --config-dir <path>` that calls `factory.curator.interface.scan_rom_directory` (the public Polylith facade — `factory.curator.runtime.*` does not expose it), prints a JSON summary, and persists a scan report under the config dir. Must respect `OPENARCADE_NO_FIXTURES=1` to skip the wall's fixture tree
- [ ] 3.4 Implement `openarcade launch <game-id> --config-dir <path>` that resolves the tile via the wall's `launch_intent`, sends the NCI command, polls `GetStatusProbe` for up to 5 s, and exits 0 on `PLAYING` or 1 on timeout
- [ ] 3.5 Register the CLI as the `openarcade` console script in `pyproject.toml` under `[project.scripts]`
- [ ] 3.6 Write a `test/test_cli.py` smoke test that invokes each subcommand with `--help` and asserts the exit code is 0

## 4. Environment-variable contract

- [ ] 4.1 Implement `factory.openarcade.env.resolve_config_dir(cli_value: str | None) -> Path` with priority: explicit `--config-dir` > `OPENARCADE_CONFIG_DIR` > `./openarcade_config` (CWD-relative). Asserts the resolved path is never under `$HOME` (raises `ValueError` if it is)
- [ ] 4.2 Implement `factory.openarcade.env.resolve_nci_target(cli_host: str | None, cli_port: int | None) -> tuple[str, int]` with priority: flags > env > defaults (`127.0.0.1`, `55355`)
- [ ] 4.3 Write `test/test_env.py` covering all three resolution layers for both config-dir and NCI target, plus the `$HOME`-rejection guard

## 5. Composition wiring

- [ ] 5.1 Add `factory.openarcade.composition.build_di_container(config_dir)` that returns the assembled `Navigator` + `ConfigService` + `CuratorBridge` instances the wall needs
- [ ] 5.2 Add a `declared-bricks` list to `BRICK.yaml` under a new top-level field (this is a project-local convention — `bricks_consumed` is not a Polylith-standard field). Enumerate: `launch`, `library`, `arcade_config`, `state`, `curator`, `ui`
- [ ] 5.3 Implement an `undeclared-import` CI guard: walk `bases/openarcade/src/**/*.py` with `ast`, collect every `factory.<x>` import, and assert `<x>` is in `BRICK.yaml`'s `declared-bricks` list. Fail the build with a message naming the undeclared brick. Place the guard at `bases/openarcade/test/test_undeclared_imports.py` so `pytest` picks it up. This is the sole enforcement mechanism (it does not depend on `foreman resolve-deps`, which operates on AST independently of `BRICK.yaml`)
- [ ] 5.4 Reuse the wall's existing pure modules (`focus.py`, `filters.py`, `chrome.py`, `components.py`) without modification — composition only imports them via `factory.<brick>.interface` (per Decision #1, except `factory.ui` which uses `factory.ui.runtime.adapters.flet_adapter`)

## 6. Backward-compatible entry points

- [ ] 6.1 Rewrite `projects/openarcade/main.py` to a 5-line wrapper: `from factory.openarcade import run_wall; run_wall()`
- [ ] 6.2 Rewrite `projects/openarcade/run.sh` to set the existing `PYTHONPATH` + `OPENARCADE_CONFIG_DIR` defaults, then `exec python -m factory.openarcade "$@"`
- [ ] 6.3 Rewrite `projects/openarcade/run_web.sh` to call `openarcade run --config-dir "${OPENARCADE_CONFIG_DIR:-./openarcade_config}"` (preserving its prior port-binding env vars)
- [ ] 6.4 Add a fallback path: if `factory.openarcade` is not importable (e.g. partial deploy), the shell scripts MUST fall back to the pre-base `PYTHONPATH`-based invocation so rollback is safe
- [ ] 6.5 Smoke test all three wrappers in a clean shell and confirm the wall launches identically to the pre-base behavior

## 7. CI and validation

- [ ] 7.1 Add a GitHub Actions step (or local `make` target) running `foreman check` on the new base
- [ ] 7.2 Wire the undeclared-import guard from task 5.3 into CI: `pytest bases/openarcade/test/test_undeclared_imports.py` runs on every PR and on `main`. A failure exits non-zero with the undeclared brick's name. (Implementation is in 5.3; this task is the CI plumbing only.)
- [ ] 7.3 Run `openspec validate add-openarcade-base --strict` and confirm zero errors
- [ ] 7.4 Run the existing wall test suite (`cd projects/openarcade && pytest wall -q`) and the new base test suite (`cd bases/openarcade && pytest -q`) and confirm all pass
- [ ] 7.5 Manually launch the wall in a desktop session and verify keyboard nav, detail page, launch, and config write/read all behave identically to the pre-base behavior

## 8. Documentation and handoff

- [ ] 8.1 Add `bases/openarcade/README.md` covering: install (`pip install -e bases/openarcade`), run (`openarcade run`), scan (`openarcade scan <dir>`), launch (`openarcade launch <id>`), env vars, and the lean-deps contract
- [ ] 8.2 Update `projects/openarcade/ARCHITECTURE.md` with a "Base composition" section pointing to `bases/openarcade/` and the entry-point diagram
- [ ] 8.3 Update `projects/openarcade/HANDOFF.md` with the migration steps so the human rebasing `feat/openarcade-build` knows what to fold in
- [ ] 8.4 Run `/opsx:archive` to move the change to `openspec/changes/archive/` and sync the `openarcade-base` spec into `openspec/specs/openarcade-base/spec.md`

## 9. Open questions to resolve before/during implementation

- [ ] 9.1 Confirm with the human whether the `python -m factory.openarcade` console script should be registered in addition to (or instead of) the Typer `openarcade` CLI
- [ ] 9.2 (RESOLVED by meta-architect review) The undeclared-import guard ships in this change as task 5.3 + 7.2 — the spec's "Composition is auditable" requirement mandates it
- [ ] 9.3 Confirm whether `feat/openarcade-build` should be rebased on top of this base before or after `/opsx:archive`
