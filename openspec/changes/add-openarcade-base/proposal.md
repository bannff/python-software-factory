## Why

OpenArcade currently lives as a sibling Polylith project under `projects/openarcade/`
with control-plane bricks in `components/` (`launch`, `library`, `arcade_config`,
`state`, `curator`) and a Flet UI shell in `projects/openarcade/wall/`. Every other
sub-project in this monorepo has a corresponding `bases/<name>/` deployable unit
(`api`, `blueprint`, `dashboard`, `mcp_server`, `worker`, `pipeline_dataset`,
`flet_dashboard`). OpenArcade has none — there is no `pyproject.toml` that names
its concrete dependencies, no `BRICK.yaml` declaring it as a base, and no canonical
entry point that wires the wall + control-plane bricks together. This means
deployers (Docker, CI, future kiosk installer) cannot `pip install` or `python -m`
an "openarcade" deliverable. We need a base.

## What Changes

- Add `bases/openarcade/` containing:
  - `BRICK.yaml` declaring `type: base`, `namespace: factory.openarcade`, and the
    list of consumed bricks (`launch`, `library`, `arcade_config`, `state`,
    `curator`, `ui`) with the Flet adapter feature flag.
  - `pyproject.toml` declaring the lean runtime deps (`flet`, `pydantic`,
    `structlog`, `typer`, `pyyaml`) and the brick source paths.
  - `src/factory/openarcade/__init__.py` re-exporting the public surface
    (`build_app`, `run_wall`, `NciTransport`, `GetStatusProbe`).
  - `src/factory/openarcade/app.py` — the entry point that composes the wall's
    `navigator` + `fixtures` + `config_service` + `curator_bridge` against the
    control-plane bricks' concrete `runtime` modules.
  - `src/factory/openarcade/cli.py` — Typer CLI (`openarcade run`,
    `openarcade scan`, `openarcade launch`) for headless / scripted use.
  - `test/` — pure-function tests for the assembly wiring (DI container, config
    resolution, fixture tree, launch-intent guard).
- Move `projects/openarcade/main.py`, `projects/openarcade/run.sh`, and
  `projects/openarcade/run_web.sh` into the base as thin wrappers that call
  `factory.openarcade:run_wall()` / `factory.openarcade.cli:main`. Keep the
  shell scripts as compatibility shims that re-export the same env vars
  (`OPENARCADE_CONFIG_DIR`, `PYTHONPATH`).
- Add `bases/openarcade` to the monorepo's polylith workspace wiring (poly
  `info` / `foreman` will pick it up automatically once the `BRICK.yaml` exists;
  no top-level `pyproject.toml` change expected).
- Document the migration in `projects/openarcade/HANDOFF.md` so the existing
  uncommitted branch (`feat/openarcade-build`) can fold in the new layout.

## Capabilities

### New Capabilities

- `openarcade-base`: The deployable base for OpenArcade. Defines the public
  Python API (`factory.openarcade`), the CLI surface, the entry-point
  composition rules (which control-plane bricks get wired into the wall),
  and the contract for environment variables (`OPENARCADE_CONFIG_DIR`,
  `OPENARCADE_NCI_HOST`, `OPENARCADE_NCI_PORT`).

### Modified Capabilities

- None. No existing OpenSpec capability exists yet (this is the first spec
  written in this repo), so no delta is needed against any prior capability.

## Impact

- **New directory**: `bases/openarcade/` (new top-level Polylith base).
- **Moved code**: `projects/openarcade/main.py` and the two shell scripts
  become thin shims; behavior identical.
- **Bricks consumed**: `launch`, `library`, `arcade_config`, `state`, `curator`,
  `ui` (Flet adapter). No brick code changes required — only the
  import-surface resolution (must use `factory.<brick>.runtime.*`, never
  `factory.<brick>.interface` per the lean-env note).
- **Dependencies**: No new third-party deps — the lean set is already
  declared on `projects/openarcade/pyproject.toml`. The base reuses it.
- **CI**: The GitHub Actions matrix will gain one more base to test
  (`bases/openarcade/test`). Local pytest invocation moves from
  `cd projects/openarcade && pytest wall` to `cd bases/openarcade && pytest`
  with a backward-compat shim.
- **Parked work unaffected**: The real-hardware NCI handoff spike
  (`projects/openarcade/spike/`) and the Brook Neo-Arcade udev validation
  stay where they are.
